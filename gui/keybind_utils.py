"""Layout-independent Ctrl+<letter> keybinding (Windows only).

Tkinter's "<Control-c>"-style bindings match on keysym, which Windows derives
from the character the *current keyboard layout* maps to that physical key.
Under a Thai layout the physical C/V keys don't produce keysym 'c'/'v', so
those bindings silently never fire. Binding on "<Control-Key>" and checking
event.keycode (the Windows virtual-key code of the physical key) instead
sidesteps this, since keycode is layout-independent — VK_A..VK_Z equal the
ASCII codes of 'A'..'Z' regardless of what layout is active.
"""


def bind_ctrl_key(widget, letter: str, callback):
    """Bind Ctrl+<letter> on `widget` so it fires under any keyboard layout.

    `letter` is a single ASCII letter, e.g. "C" or "V".
    `callback` is invoked with no arguments.
    """
    vk = ord(letter.upper())

    def _handler(event):
        if event.keycode == vk:
            callback()

    widget.bind("<Control-Key>", _handler, add="+")
