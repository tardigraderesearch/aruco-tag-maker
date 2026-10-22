"""Desktop app (tkinter + ttk). All real logic lives in plain modules; this file
only wires widgets to settings.py / exporter.py / verify.py."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import __version__, theme
from .exporter import existing_conflicts, export
from .marker import marker_image
from .platform_utils import enable_hidpi, open_folder
from .settings import (
    DEFAULT_DICTIONARY,
    DICTIONARIES,
    MAX_TAGS,
    MAX_TAG_MM,
    MIN_TAG_MM,
    MIN_TAGS,
    PAGE_SIZE,
    Settings,
    ValidationError,
    page_bounds,
    page_count,
    page_of,
    validate_count,
    validate_names,
)
from .verify import verify_folder

THUMB_PX = 48
ERROR_FG = theme.ERROR
DEFAULT_COUNT = 10


class TagMakerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(f"ArUco Tag Maker {__version__}")
        root.minsize(820, 640)
        root.geometry("940x760")
        self.names: list[str] = [""] * DEFAULT_COUNT
        self.page = 0
        self.errors: dict[int, str] = {}
        self.show_all_errors = False
        self.touched: set[int] = set()
        self._thumbs: dict[tuple[str, int, int], ImageTk.PhotoImage] = {}
        self._events: queue.Queue = queue.Queue()
        self._loading_page = False
        self.busy = False

        defaults = Settings()
        self.count_var = tk.StringVar(value=str(DEFAULT_COUNT))
        self.size_var = tk.StringVar(value=f"{defaults.tag_size_mm:g}")
        self.dict_var = tk.StringVar(value=DEFAULT_DICTIONARY)
        self.quiet_var = tk.StringVar(value=str(defaults.quiet_zone_modules))
        self.base_var = tk.StringVar(value=f"{defaults.base_thickness_mm:g}")
        self.relief_var = tk.StringVar(value=f"{defaults.relief_mm:g}")
        self.start_var = tk.StringVar(value=str(defaults.start_id))
        self.engrave_var = tk.BooleanVar(value=defaults.engrave_names)
        self.depth_var = tk.StringVar(value=f"{defaults.engrave_depth_mm:g}")
        self.folder_var = tk.StringVar(value=str(Path.home() / "aruco-tags"))
        self.count_error = tk.StringVar()
        self.settings_error = tk.StringVar()
        self.size_hint = tk.StringVar()
        self.page_label = tk.StringVar()
        self.page_errors = tk.StringVar()
        self.status = tk.StringVar(value="Name your tags, pick a folder, then Generate.")

        self._build()
        for var in (self.size_var, self.dict_var, self.quiet_var, self.base_var,
                    self.relief_var, self.start_var, self.depth_var):
            var.trace_add("write", lambda *_: self._settings_changed())
        self.engrave_var.trace_add("write", lambda *_: self._settings_changed())
        self.count_var.trace_add("write", lambda *_: self._count_changed())
        self._settings_changed()
        self._show_page()
        root.after(50, self._poll_events)

    # ---------------------------------------------------------------- layout
    def _build(self) -> None:
        root = self.root
        theme.apply(root)

        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        # 1. count + size, front and centre
        top = ttk.Frame(outer)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="How many tags?", style="Big.TLabel").grid(row=0, column=0, sticky="w")
        self.count_spin = ttk.Spinbox(top, from_=MIN_TAGS, to=MAX_TAGS, width=5,
                                      textvariable=self.count_var)
        self.count_spin.grid(row=0, column=1, padx=(6, 18))
        ttk.Label(top, text="Tag size (mm)", style="Big.TLabel").grid(row=0, column=2, sticky="w")
        self.size_spin = ttk.Spinbox(top, from_=MIN_TAG_MM, to=MAX_TAG_MM, increment=1, width=7,
                                     textvariable=self.size_var)
        self.size_spin.grid(row=0, column=3, padx=6)
        ttk.Label(top, textvariable=self.size_hint, style="Muted.TLabel").grid(row=0, column=4, sticky="w")
        ttk.Label(top, textvariable=self.count_error, style="Error.TLabel").grid(
            row=1, column=0, columnspan=5, sticky="w")

        # 2. options
        opts = ttk.LabelFrame(outer, text="Options", padding=(10, 6))
        opts.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        row = ttk.Frame(opts)
        row.pack(fill="x")
        ttk.Label(row, text="Dictionary").pack(side="left")
        ttk.Combobox(row, textvariable=self.dict_var, values=list(DICTIONARIES), width=19,
                     state="readonly").pack(side="left", padx=(4, 12))
        self._small_spin(row, "Border (modules)", self.quiet_var, 1, 4, 1, 3)
        self._small_spin(row, "Base (mm)", self.base_var, 0.6, 20, 0.2, 5)
        self._small_spin(row, "Relief (mm)", self.relief_var, 0.1, 5, 0.1, 5)
        self._small_spin(row, "First ID", self.start_var, 0, 999, 1, 5)
        row2 = ttk.Frame(opts)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(row2, text="Engrave name on the back (never on the marker face)",
                        variable=self.engrave_var).pack(side="left")
        self._small_spin(row2, "  depth (mm)", self.depth_var, 0.1, 5, 0.1, 5)
        ttk.Label(opts, textvariable=self.settings_error, style="Error.TLabel").pack(anchor="w")

        # 3. paginated tag list
        listbox = ttk.LabelFrame(outer, text="Tags", padding=(6, 4))
        listbox.grid(row=2, column=0, sticky="nsew")
        listbox.columnconfigure(0, weight=1)
        listbox.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(listbox, highlightthickness=0, borderwidth=0, background=theme.BG)
        scroll = ttk.Scrollbar(listbox, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.rows_frame = ttk.Frame(self.canvas)
        self._rows_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.rows_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._rows_window, width=e.width))
        self._bind_mousewheel(self.canvas)

        self.row_widgets = []
        for slot in range(PAGE_SIZE):
            frame = ttk.Frame(self.rows_frame, padding=(2, 2))
            thumb = ttk.Label(frame)
            thumb.grid(row=0, column=0, padx=(0, 10))
            label = ttk.Label(frame, width=14)
            label.grid(row=0, column=1, sticky="w")
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=30)
            entry.grid(row=0, column=2, sticky="w")
            err = ttk.Label(frame, style="Error.TLabel")
            err.grid(row=0, column=3, sticky="w", padx=(10, 0))
            var.trace_add("write", lambda *_, s=slot: self._name_edited(s))
            self._bind_mousewheel(frame)
            self.row_widgets.append({"frame": frame, "thumb": thumb, "label": label,
                                     "var": var, "entry": entry, "error": err})

        nav = ttk.Frame(listbox)
        nav.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.prev_btn = ttk.Button(nav, text="< Prev", command=lambda: self.go_page(self.page - 1))
        self.prev_btn.pack(side="left")
        ttk.Label(nav, textvariable=self.page_label).pack(side="left", padx=10)
        self.next_btn = ttk.Button(nav, text="Next >", command=lambda: self.go_page(self.page + 1))
        self.next_btn.pack(side="left")
        ttk.Label(nav, textvariable=self.page_errors, style="Error.TLabel").pack(side="left", padx=10)
        ttk.Button(nav, text="Fill empty names", command=self.fill_empty).pack(side="right")

        # 4. export
        bottom = ttk.Frame(outer)
        bottom.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        bottom.columnconfigure(1, weight=1)
        ttk.Label(bottom, text="Export to").grid(row=0, column=0, sticky="w")
        ttk.Entry(bottom, textvariable=self.folder_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(bottom, text="Browse...", command=self.browse).grid(row=0, column=2)
        self.generate_btn = ttk.Button(bottom, text="Generate", style="Accent.TButton",
                                       command=self.generate)
        self.generate_btn.grid(row=0, column=3, padx=(10, 0))
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 2))
        ttk.Label(bottom, textvariable=self.status).grid(row=2, column=0, columnspan=4, sticky="w")

    def _small_spin(self, parent, text, var, lo, hi, step, width) -> None:
        ttk.Label(parent, text=text).pack(side="left")
        ttk.Spinbox(parent, from_=lo, to=hi, increment=step, width=width,
                    textvariable=var).pack(side="left", padx=(4, 12))

    def _bind_mousewheel(self, widget) -> None:
        widget.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(
            -1 if e.delta > 0 else 1, "units"))
        widget.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        widget.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    # ---------------------------------------------------------------- state
    def current_settings(self) -> Settings:
        return Settings.from_dict({
            "dictionary": self.dict_var.get(),
            "tag_size_mm": self.size_var.get(),
            "quiet_zone_modules": self.quiet_var.get(),
            "base_thickness_mm": self.base_var.get(),
            "relief_mm": self.relief_var.get(),
            "start_id": self.start_var.get(),
            "engrave_names": self.engrave_var.get(),
            "engrave_depth_mm": self.depth_var.get(),
        })

    def _settings_or_none(self) -> Settings | None:
        try:
            settings = self.current_settings()
        except ValidationError as exc:
            msgs = exc.details.get("settings", {})
            self.settings_error.set("; ".join(msgs.values()) or str(exc))
            self.size_hint.set("")
            return None
        self.settings_error.set("")
        self.size_hint.set(f"black square {settings.tag_size_mm:g} mm, printed tile "
                           f"{settings.tile_size_mm:.4g} mm with border")
        return settings

    def _settings_changed(self) -> None:
        if self._settings_or_none() is not None:
            self._show_page()

    def _count_changed(self) -> None:
        try:
            count = validate_count(self.count_var.get())
        except ValidationError as exc:
            self.count_error.set(str(exc))
            return
        self.count_error.set("")
        self.set_count(count)

    def set_count(self, count: int) -> None:
        if count < len(self.names):
            del self.names[count:]
        else:
            self.names.extend([""] * (count - len(self.names)))
        if self.count_var.get().strip() != str(count):
            self.count_var.set(str(count))
        self.page = min(self.page, page_count(count) - 1)
        self._revalidate()
        self._show_page()

    @property
    def pages(self) -> int:
        return page_count(len(self.names))

    def go_page(self, page: int) -> None:
        if 0 <= page < self.pages:
            self.page = page
            self._show_page()
            self.canvas.yview_moveto(0)

    def _thumbnail(self, settings: Settings, marker_id: int):
        key = (settings.dictionary, marker_id, settings.quiet_zone_modules)
        if key not in self._thumbs:
            ppm = max(2, THUMB_PX // settings.total_modules)
            array = marker_image(settings.dictionary, marker_id, settings.quiet_zone_modules, ppm)
            self._thumbs[key] = ImageTk.PhotoImage(Image.fromarray(array), master=self.root)
        return self._thumbs[key]

    def _show_page(self) -> None:
        settings = self._settings_or_none()
        if settings is None or not self.names:
            return
        start, end = page_bounds(self.page, len(self.names))
        self._loading_page = True
        try:
            for slot, widgets in enumerate(self.row_widgets):
                index = start + slot
                if index >= end:
                    widgets["frame"].grid_forget()
                    continue
                widgets["frame"].grid(row=slot, column=0, sticky="ew")
                marker_id = settings.start_id + index
                if marker_id < settings.dictionary_size:
                    widgets["thumb"].configure(image=self._thumbnail(settings, marker_id))
                    widgets["label"].configure(text=f"Tag {index + 1}   ID {marker_id}")
                else:
                    widgets["thumb"].configure(image="")
                    widgets["label"].configure(text=f"Tag {index + 1}   (no ID)")
                widgets["var"].set(self.names[index])
        finally:
            self._loading_page = False
        self.page_label.set(f"Page {self.page + 1} of {self.pages}")
        self.prev_btn.state(["!disabled"] if self.page > 0 else ["disabled"])
        self.next_btn.state(["!disabled"] if self.page < self.pages - 1 else ["disabled"])
        self._paint_errors()

    def _name_edited(self, slot: int) -> None:
        if self._loading_page:
            return
        index = self.page * PAGE_SIZE + slot
        if index < len(self.names):
            self.names[index] = self.row_widgets[slot]["var"].get()
            self.touched.add(index)
            self._revalidate()
            self._paint_errors()

    def _revalidate(self, settings: Settings | None = None) -> bool:
        try:
            validate_names(self.names, settings)
        except ValidationError as exc:
            self.errors = {int(k): v for k, v in exc.details.get("names", {}).items()}
            if not self.errors:
                self.status.set(str(exc))
            return False
        self.errors = {}
        return True

    def _visible_error(self, index: int) -> str:
        message = self.errors.get(index, "")
        if not self.show_all_errors and index not in self.touched and message == "name is required":
            return ""
        return message

    def _paint_errors(self) -> None:
        start = self.page * PAGE_SIZE
        for slot, widgets in enumerate(self.row_widgets):
            widgets["error"].configure(text=self._visible_error(start + slot))
        bad_pages = sorted({page_of(i) + 1 for i in self.errors if self._visible_error(i)})
        self.page_errors.set(f"needs attention: page {', '.join(map(str, bad_pages))}"
                             if bad_pages else "")

    def fill_empty(self) -> None:
        width = max(2, len(str(len(self.names))))
        for index, name in enumerate(self.names):
            if not name.strip():
                candidate = f"tag_{index + 1:0{width}d}"
                taken = {n.lower() for n in self.names}
                while candidate.lower() in taken:
                    candidate += "x"
                self.names[index] = candidate
        self._revalidate()
        self._show_page()

    def browse(self) -> None:
        current = Path(self.folder_var.get()).expanduser()
        start = current if current.is_dir() else current.parent if current.parent.is_dir() else Path.home()
        chosen = filedialog.askdirectory(parent=self.root, initialdir=str(start),
                                         title="Export tags to folder", mustexist=False)
        if chosen:
            self.folder_var.set(str(Path(chosen)))

    # ---------------------------------------------------------------- export
    def validate_all(self) -> Settings | None:
        """Full validation before export. Jumps to the first page with a problem."""
        self.show_all_errors = True
        settings = self._settings_or_none()
        if settings is None:
            self.status.set("Fix the options marked in red.")
            return None
        try:
            validate_count(self.count_var.get())
        except ValidationError as exc:
            self.count_error.set(str(exc))
            return None
        ok = self._revalidate(settings)
        if not ok:
            if self.errors:
                first = min(self.errors)
                self.status.set(f"{len(self.errors)} name(s) need attention.")
                if page_of(first) != self.page:
                    self.go_page(page_of(first))
            self._paint_errors()
            return None
        self._paint_errors()
        return settings

    def generate(self) -> None:
        if self.busy:
            return
        settings = self.validate_all()
        if settings is None:
            return
        folder_text = self.folder_var.get().strip()
        if not folder_text:
            messagebox.showerror("Export folder", "Choose a folder to export to.", parent=self.root)
            return
        folder = Path(folder_text).expanduser()
        if folder.exists() and not folder.is_dir():
            messagebox.showerror("Export folder", f"{folder} is a file, not a folder.", parent=self.root)
            return
        names = list(self.names)
        conflicts = existing_conflicts(names, folder)
        if conflicts and not messagebox.askyesno(
            "Overwrite files?",
            f"{len(conflicts)} file(s) already exist in\n{folder}\n\n"
            f"for example {conflicts[0].relative_to(folder)}.\n\nOverwrite them?",
            icon="warning", parent=self.root,
        ):
            self.status.set("Export cancelled; nothing was written.")
            return
        self._set_busy(True)
        self.progress.configure(maximum=len(names) + 1, value=0)
        threading.Thread(target=self._worker, args=(names, settings, folder), daemon=True).start()

    def _worker(self, names: list[str], settings: Settings, folder: Path) -> None:
        try:
            export(names, settings, folder, overwrite=True,
                   progress=lambda done, total, name: self._events.put(("progress", done, name)))
            self._events.put(("progress", len(names), "verifying"))
            verify_folder(folder, log=lambda _msg: None)
            self._events.put(("done", folder, len(names)))
        except Exception as exc:  # noqa: BLE001 - reported to the user
            self._events.put(("error", f"{type(exc).__name__}: {exc}"))

    def _poll_events(self) -> None:
        try:
            while True:
                event = self._events.get_nowait()
                if event[0] == "progress":
                    _, done, name = event
                    self.progress.configure(value=done)
                    label = "Checking every tag decodes..." if name == "verifying" else f"Building {name}..."
                    self.status.set(label if name != "done" else "Writing markers.json / markers.py...")
                elif event[0] == "done":
                    _, folder, count = event
                    self.progress.configure(value=self.progress["maximum"])
                    self._set_busy(False)
                    self.status.set(f"Exported and verified {count} tags in {folder}")
                    self._success_dialog(folder, count)
                elif event[0] == "error":
                    self._set_busy(False)
                    self.status.set("Export failed.")
                    messagebox.showerror("Export failed", event[1], parent=self.root)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(50, self._poll_events)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.generate_btn.state(["disabled"] if busy else ["!disabled"])
        self.root.configure(cursor="watch" if busy else "")

    def _success_dialog(self, folder: Path, count: int) -> None:
        dialog = tk.Toplevel(self.root, background=theme.BG)
        dialog.title("Export complete")
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"{count} tags exported and verified", style="Big.TLabel").pack(anchor="w")
        ttk.Label(frame, text=str(folder.resolve())).pack(anchor="w", pady=(4, 2))
        ttk.Label(frame, text="stl/  png/  markers.json  markers.py", style="Muted.TLabel").pack(anchor="w")
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(12, 0))

        def _open() -> None:
            try:
                open_folder(folder)
            except OSError as exc:
                messagebox.showerror("Open folder", str(exc), parent=dialog)

        ttk.Button(buttons, text="Open folder", command=_open).pack(side="left")
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="right")
        dialog.grab_set()


def run() -> int:
    enable_hidpi()
    root = tk.Tk()
    TagMakerApp(root)
    root.mainloop()
    return 0
