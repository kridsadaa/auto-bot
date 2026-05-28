# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("config/bot_config.example.yaml", "config"),
    ],
    hiddenimports=[
        "cv2",
        "PIL._tkinter_finder",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "win32com.client",
        "win32api",
        "win32con",
        "keyboard",
        "pywinauto",
        "pandas",
        "yaml",
        "playwright.sync_api",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "pytest_mock"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="AutoBot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # ซ่อน console window
    onefile=True,        # รวมเป็น .exe เดียว
    icon=None,
)
