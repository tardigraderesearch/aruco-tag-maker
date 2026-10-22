"""Command line entry point.

    aruco-tag-maker                      open the desktop app
    aruco-tag-maker generate --names F   scripting path, no window
    aruco-tag-maker verify FOLDER        re-check an exported folder
    aruco-tag-maker doctor               check this computer can run it
"""

from __future__ import annotations

import argparse
import importlib
import platform
import sys
from pathlib import Path

from . import __version__
from .settings import DEFAULT_DICTIONARY, DICTIONARIES, Settings, ValidationError


def _settings_args(parser: argparse.ArgumentParser) -> None:
    d = Settings()
    parser.add_argument("--dictionary", default=DEFAULT_DICTIONARY, choices=sorted(DICTIONARIES))
    parser.add_argument("--tag-size", type=float, default=d.tag_size_mm, metavar="MM",
                        help="side of the black square in mm (default %(default)s)")
    parser.add_argument("--quiet-zone", type=int, default=d.quiet_zone_modules, metavar="MODULES",
                        help="white border width in marker modules (default %(default)s)")
    parser.add_argument("--base", type=float, default=d.base_thickness_mm, metavar="MM",
                        help="white base thickness (default %(default)s)")
    parser.add_argument("--relief", type=float, default=d.relief_mm, metavar="MM",
                        help="height of the raised black pattern (default %(default)s)")
    parser.add_argument("--start-id", type=int, default=d.start_id,
                        help="id of the first tag (default %(default)s)")
    parser.add_argument("--engrave", action=argparse.BooleanOptionalAction, default=d.engrave_names,
                        help="engrave each name into the back of its tile (default on)")
    parser.add_argument("--engrave-depth", type=float, default=d.engrave_depth_mm, metavar="MM")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aruco-tag-maker", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="open the desktop app (default)")

    gen = sub.add_parser("generate", help="export tags from a names file without the GUI")
    gen.add_argument("--names", required=True, type=Path, help="text file, one tag name per line")
    gen.add_argument("--out", "-o", type=Path, default=Path("aruco-tags"), help="output folder")
    gen.add_argument("--overwrite", action="store_true", help="replace existing files")
    gen.add_argument("--no-verify", action="store_true", help="skip the detection check afterwards")
    _settings_args(gen)

    ver = sub.add_parser("verify", help="re-check an exported folder")
    ver.add_argument("folder", type=Path)

    sub.add_parser("doctor", help="check Python, libraries and Tk")
    return parser


def cmd_generate(args: argparse.Namespace) -> int:
    from .exporter import export
    from .names_file import read_names
    from .verify import VerificationError, verify_folder

    try:
        names = read_names(args.names)
        settings = Settings.from_dict({
            "dictionary": args.dictionary,
            "tag_size_mm": args.tag_size,
            "quiet_zone_modules": args.quiet_zone,
            "base_thickness_mm": args.base,
            "relief_mm": args.relief,
            "start_id": args.start_id,
            "engrave_names": args.engrave,
            "engrave_depth_mm": args.engrave_depth,
        })

        def progress(done: int, total: int, name: str) -> None:
            if done < total:
                print(f"  [{done + 1:2d}/{total}] {name}", flush=True)

        result = export(names, settings, args.out, overwrite=args.overwrite, progress=progress)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        for group in exc.details.values():
            for key, message in group.items():
                label = f"line {int(key) + 1}" if key.isdigit() else key
                print(f"  {label}: {message}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        hint = " (use --overwrite to replace them)" if isinstance(exc, FileExistsError) else ""
        print(f"error: {exc}{hint}", file=sys.stderr)
        return 2
    print(f"Wrote {len(result.tags)} tags to {result.folder.resolve()}")
    if not args.no_verify:
        try:
            verify_folder(result.folder)
        except VerificationError as exc:
            print(f"verification FAILED: {exc}", file=sys.stderr)
            return 1
    return 0


def cmd_doctor() -> int:
    ok = True
    print(f"Python {platform.python_version()} on {platform.system()} {platform.machine()}")
    if sys.version_info < (3, 11):
        print("  !! Python 3.11 or newer is required")
        ok = False
    for module, package in (("numpy", "numpy"), ("cv2", "opencv-python-headless"),
                            ("manifold3d", "manifold3d"), ("PIL", "Pillow")):
        try:
            mod = importlib.import_module(module)
            print(f"  ok  {package} {getattr(mod, '__version__', '')}".rstrip())
        except ImportError as exc:
            print(f"  !!  {package} missing ({exc}); run: python -m pip install {package}")
            ok = False
    try:
        import tkinter

        print(f"  ok  tkinter (Tk {tkinter.TkVersion})")
    except ImportError:
        from .platform_utils import tkinter_fix_hint

        print("  !!  tkinter missing; the desktop app needs it. " + tkinter_fix_hint())
        ok = False
    print("All good." if ok else "Some checks failed (see !! above).")
    return 0 if ok else 1


def cmd_gui() -> int:
    try:
        import tkinter
    except ImportError:
        from .platform_utils import tkinter_fix_hint

        print("tkinter is not available, so the window cannot open.\n" + tkinter_fix_hint(),
              file=sys.stderr)
        print("The scripting path still works: aruco-tag-maker generate --names names.txt",
              file=sys.stderr)
        return 3
    from .gui import run

    try:
        return run()
    except tkinter.TclError as exc:
        print(f"Could not open a window: {exc}\n"
              "Run this from a desktop session (on a headless machine use "
              "'aruco-tag-maker generate --names names.txt').", file=sys.stderr)
        return 3


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        return cmd_generate(args)
    if args.command == "verify":
        from .verify import main as verify_main

        return verify_main([str(args.folder)])
    if args.command == "doctor":
        return cmd_doctor()
    return cmd_gui()
