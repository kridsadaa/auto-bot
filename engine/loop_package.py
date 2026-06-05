"""
Export / Import loop เป็นแพ็กไฟล์เดียว (.botpack = zip) ที่มีรูปครบ
แชร์ให้คนอื่น import แล้วรันได้เลย

ความปลอดภัย: ค่าตัวแปรถูกล้างเป็นค่าว่างเสมอ (ไม่ส่ง PASSWORD); CSV แนบเฉพาะเมื่อสั่ง
"""
import copy
import os
import re
import zipfile

import yaml

from engine.logger import get_logger

MANIFEST_NAME = "manifest.yaml"
ASSETS_DIR = "assets"
FORMAT = "autobot-loop"


# ─── walker: เดินทุก image target รวมสาขาซ้อน ─────────────────────────────────

def _walk_targets(steps, fn):
    """เรียก fn(container, key) สำหรับทุกฟิลด์ 'target' ที่เป็นรูป (รวม then/else/switch cases)"""
    for step in steps or []:
        if isinstance(step.get("target"), str):
            fn(step, "target")
        for branch in ("then", "else", "default"):
            if isinstance(step.get(branch), list):
                _walk_targets(step[branch], fn)
        for case in step.get("cases", []) or []:
            if isinstance(case.get("target"), str):
                fn(case, "target")
            _walk_targets(case.get("steps", []) or [], fn)


def _sanitize(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(name)) or "loop"


def _collect_var_names(steps) -> set:
    """หาชื่อตัวแปรที่ loop ใช้ จาก {NAME} ใน text ของ step type (ข้าม csv.* และ TODAY*)"""
    names: set = set()

    def scan(step_list):
        for step in step_list or []:
            if step.get("action") == "type" and isinstance(step.get("text"), str):
                for m in re.findall(r"\{([^}]+)\}", step["text"]):
                    if m.startswith("csv.") or m in ("TODAY", "TODAY_ISO"):
                        continue
                    names.add(m)
            for branch in ("then", "else", "default"):
                if isinstance(step.get(branch), list):
                    scan(step[branch])
            for case in step.get("cases", []) or []:
                scan(case.get("steps", []) or [])

    scan(steps)
    return names


# ─── EXPORT ───────────────────────────────────────────────────────────────────

def build_package(config: dict, loop_name: str, out_path: str, include_data: bool = False) -> dict:
    """สร้าง .botpack จาก loop หนึ่งตัว — คืน summary {assets, missing, variables, states}"""
    loops = config.get("loops", {})
    if loop_name not in loops:
        raise ValueError(f"ไม่พบ loop: {loop_name}")

    loop_cfg = copy.deepcopy(loops[loop_name])
    states = [copy.deepcopy(s) for s in config.get("states", []) if s.get("loop") == loop_name]

    # ตัวแปรที่ใช้ → ค่าว่างเสมอ (ความปลอดภัย); รวมชื่อตัวแปรเฉพาะ loop ด้วย
    var_names = _collect_var_names(loop_cfg.get("steps", []))
    var_names |= set(loop_cfg.get("variables", {}) or {})
    variables = {name: "" for name in sorted(var_names)}
    # ล้างค่า loop-scoped variables เป็นว่าง (เก็บแค่ "ชื่อ" — กันค่า sensitive หลุดเหมือน global)
    if isinstance(loop_cfg.get("variables"), dict):
        loop_cfg["variables"] = {k: "" for k in loop_cfg["variables"]}

    # รวม path รูปทั้งหมด (loop targets + state triggers + data_source ถ้าแนบ)
    src_paths: list = []

    def collect(container, key):
        src_paths.append(container[key])

    _walk_targets(loop_cfg.get("steps", []), collect)
    for st in states:
        f = st.get("trigger", {}).get("file")
        if isinstance(f, str):
            src_paths.append(f)
    data_path = loop_cfg.get("data_source") if include_data else None
    if data_path:
        src_paths.append(data_path)

    # สร้าง mapping: path เดิม → assets/<basename> (กันชื่อชน)
    mapping: dict = {}
    used: set = set()
    for p in src_paths:
        norm = p.replace("\\", "/")
        if norm in mapping:
            continue
        base = os.path.basename(norm)
        name, ext = os.path.splitext(base)
        cand = base
        i = 1
        while cand in used:
            cand = f"{name}_{i}{ext}"
            i += 1
        used.add(cand)
        mapping[norm] = f"{ASSETS_DIR}/{cand}"

    # rewrite path ใน loop/states/data_source
    def rewrite(container, key):
        container[key] = mapping[container[key].replace("\\", "/")]

    _walk_targets(loop_cfg.get("steps", []), rewrite)
    for st in states:
        f = st.get("trigger", {}).get("file")
        if isinstance(f, str):
            st["trigger"]["file"] = mapping[f.replace("\\", "/")]
    if data_path:
        loop_cfg["data_source"] = mapping[data_path.replace("\\", "/")]
    elif "data_source" in loop_cfg:
        loop_cfg.pop("data_source")  # ไม่แนบข้อมูล → ตัด data_source ออก

    manifest = {
        "format": FORMAT,
        "version": 1,
        "name": loop_name,
        "loop": loop_cfg,
        "variables": variables,
        "states": states,
    }

    missing: list = []
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
        for norm, arc in mapping.items():
            if os.path.exists(norm):
                zf.write(norm, arc)
            else:
                missing.append(norm)

    get_logger().info(f"Exported loop '{loop_name}' → {out_path} ({len(mapping)} assets, {len(missing)} missing)")
    return {
        "out_path": out_path,
        "assets": list(mapping.values()),
        "missing": missing,
        "variables": list(variables.keys()),
        "states": [s.get("name") for s in states],
    }


# ─── IMPORT ─────────────────────────────────────────────────────────────────

def _unique_key(name: str, existing) -> str:
    if name not in existing:
        return name
    if f"{name}_imported" not in existing:
        return f"{name}_imported"
    i = 2
    while f"{name}_{i}" in existing:
        i += 1
    return f"{name}_{i}"


def import_package(config: dict, zip_path: str,
                   elements_root: str = "elements", data_root: str = "data") -> tuple:
    """แตกแพ็กเข้า config (สำเนา) — คืน (config, summary). ผู้เรียกเป็นคนเซฟ config"""
    config = copy.deepcopy(config)
    config.setdefault("loops", {})
    config.setdefault("states", [])
    config.setdefault("variables", {})

    with zipfile.ZipFile(zip_path, "r") as zf:
        manifest = yaml.safe_load(zf.read(MANIFEST_NAME).decode("utf-8")) or {}
        if manifest.get("format") != FORMAT:
            raise ValueError("ไฟล์นี้ไม่ใช่ .botpack ของ Auto Bot")

        loop_cfg = manifest.get("loop", {}) or {}
        states = manifest.get("states", []) or []
        variables = manifest.get("variables", {}) or {}

        final_name = _unique_key(manifest.get("name", "imported_loop"), config["loops"])
        importname = _sanitize(final_name)
        asset_dir = os.path.join(elements_root, importname)

        # mapping assets/<x> → elements/<importname>/<x> + แตกไฟล์
        mapping: dict = {}
        for info in zf.namelist():
            if info.startswith(ASSETS_DIR + "/") and not info.endswith("/"):
                base = os.path.basename(info)
                # data_source แยกไป data/ ; รูปไป elements/<importname>/
                dest = os.path.join(asset_dir, base)
                os.makedirs(asset_dir, exist_ok=True)
                with zf.open(info) as src, open(dest, "wb") as out:
                    out.write(src.read())
                mapping[info] = os.path.relpath(dest)

    # rewrite targets ใน loop ให้ชี้ไฟล์ที่แตกออกมา
    def rewrite(container, key):
        arc = container[key].replace("\\", "/")
        if arc in mapping:
            container[key] = mapping[arc]

    _walk_targets(loop_cfg.get("steps", []), rewrite)
    for st in states:
        f = st.get("trigger", {}).get("file")
        if isinstance(f, str) and f.replace("\\", "/") in mapping:
            st["trigger"]["file"] = mapping[f.replace("\\", "/")]

    # data_source: ย้ายไป data/<importname>_<basename> ถ้ามีและไฟล์ถูกแตกไว้
    ds = loop_cfg.get("data_source")
    if isinstance(ds, str) and ds.replace("\\", "/") in mapping:
        extracted = mapping[ds.replace("\\", "/")]
        new_ds = os.path.join(data_root, f"{importname}_{os.path.basename(extracted)}")
        os.makedirs(data_root, exist_ok=True)
        os.replace(extracted, new_ds)
        loop_cfg["data_source"] = os.path.relpath(new_ds)
    elif isinstance(ds, str) and ds.startswith(ASSETS_DIR + "/"):
        loop_cfg.pop("data_source")  # อ้าง data แต่ไม่ได้แนบมา → ตัดออก

    # merge เข้า config
    config["loops"][final_name] = loop_cfg

    added_vars = []
    for k in variables:
        if k not in config["variables"]:
            config["variables"][k] = ""  # ไม่ทับของเดิม; ค่าว่าง → ถามตอน Start
            added_vars.append(k)

    state_names = {s.get("name") for s in config["states"]}
    imported_states = []
    for st in states:
        st = copy.deepcopy(st)
        st["loop"] = final_name
        nm = _unique_key(st.get("name", "state"), state_names)
        st["name"] = nm
        state_names.add(nm)
        config["states"].append(st)
        imported_states.append(nm)

    summary = {
        "loop_name": final_name,
        "renamed": final_name != manifest.get("name"),
        "added_variables": added_vars,
        "states": imported_states,
        "asset_dir": asset_dir,
    }
    get_logger().info(f"Imported loop → '{final_name}' ({len(mapping)} assets)")
    return config, summary
