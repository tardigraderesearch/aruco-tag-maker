"""Dark, high-contrast ttk theme (near-black surfaces, warm off-white text, orange accent)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BG = "#0b0b0b"          # window background
SURFACE = "#151515"     # panels, entries
SURFACE_HI = "#1f1f1f"  # hover / raised
BORDER = "#2e2e2e"
TEXT = "#f7ece5"
MUTED = "#9a908b"
ACCENT = "#ff7a1a"
ACCENT_HI = "#ff9a4d"
ACCENT_LO = "#c85a0c"
ON_ACCENT = "#0b0b0b"
ERROR = "#ff5c5c"
FOCUS = "#ffb46b"

FONT = ("TkDefaultFont", 10)
FONT_BOLD = ("TkDefaultFont", 11, "bold")


def apply(root: tk.Misc) -> ttk.Style:
    """Install the theme on ``root`` and return the configured style."""
    style = ttk.Style(root)
    style.theme_use("clam")  # clam honours colour options on every platform

    root.configure(background=BG)
    # Classic tk widgets and popups (combobox dropdown, dialogs) follow these.
    root.option_add("*Background", BG)
    root.option_add("*Foreground", TEXT)
    root.option_add("*selectBackground", ACCENT)
    root.option_add("*selectForeground", ON_ACCENT)
    root.option_add("*TCombobox*Listbox.background", SURFACE)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", ON_ACCENT)

    style.configure(".", background=BG, foreground=TEXT, fieldbackground=SURFACE,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    troughcolor=SURFACE, focuscolor=FOCUS, insertcolor=TEXT,
                    selectbackground=ACCENT, selectforeground=ON_ACCENT, font=FONT)

    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Big.TLabel", font=FONT_BOLD)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Error.TLabel", foreground=ERROR)
    style.configure("TLabelframe", background=BG, bordercolor=BORDER, relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT, font=FONT_BOLD)

    # Buttons: flat dark with an orange edge on hover; accent button is solid orange.
    style.configure("TButton", background=SURFACE_HI, foreground=TEXT, bordercolor=BORDER,
                    lightcolor=SURFACE_HI, darkcolor=SURFACE_HI, relief="flat",
                    padding=(12, 6), font=FONT_BOLD, focusthickness=1)
    style.map("TButton",
              background=[("disabled", SURFACE), ("pressed", ACCENT_LO), ("active", "#2a2a2a")],
              foreground=[("disabled", MUTED), ("pressed", ON_ACCENT)],
              bordercolor=[("active", ACCENT), ("focus", ACCENT)],
              lightcolor=[("active", "#2a2a2a")], darkcolor=[("active", "#2a2a2a")])

    style.configure("Accent.TButton", background=ACCENT, foreground=ON_ACCENT, bordercolor=ACCENT,
                    lightcolor=ACCENT, darkcolor=ACCENT, font=("TkDefaultFont", 12, "bold"),
                    padding=(22, 9))
    style.map("Accent.TButton",
              background=[("disabled", "#5a3a22"), ("pressed", ACCENT_LO), ("active", ACCENT_HI)],
              foreground=[("disabled", "#9a7a62")],
              bordercolor=[("active", ACCENT_HI), ("focus", FOCUS)],
              lightcolor=[("active", ACCENT_HI)], darkcolor=[("active", ACCENT_HI)])

    for widget in ("TEntry", "TSpinbox", "TCombobox"):
        style.configure(widget, fieldbackground=SURFACE, foreground=TEXT, background=SURFACE_HI,
                        bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE,
                        arrowcolor=ACCENT, insertcolor=ACCENT, padding=4)
        style.map(widget,
                  bordercolor=[("focus", ACCENT), ("hover", "#4a4a4a")],
                  lightcolor=[("focus", ACCENT)],
                  fieldbackground=[("readonly", SURFACE), ("disabled", BG)],
                  foreground=[("disabled", MUTED)],
                  arrowcolor=[("disabled", MUTED), ("active", ACCENT_HI)])

    style.configure("TCheckbutton", background=BG, foreground=TEXT, indicatorbackground=SURFACE,
                    indicatorforeground=ON_ACCENT, focuscolor=BG)
    style.map("TCheckbutton",
              background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT), ("active", SURFACE_HI)])

    style.configure("Vertical.TScrollbar", background=SURFACE_HI, troughcolor=BG,
                    bordercolor=BG, arrowcolor=ACCENT, lightcolor=SURFACE_HI, darkcolor=SURFACE_HI)
    style.map("Vertical.TScrollbar", background=[("active", ACCENT_LO)])

    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=SURFACE,
                    bordercolor=BORDER, lightcolor=ACCENT, darkcolor=ACCENT, thickness=10)
    return style
