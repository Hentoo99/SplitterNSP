"""Entry point: with no arguments it opens the graphical interface."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # macOS may pass "-psn_..." to apps opened from Finder; files dropped on the
    # app icon arrive as plain paths and open in the GUI.
    argv = [a for a in argv if not a.startswith("-psn")]
    if not argv or argv[0] not in ("split", "info", "set-archive", "-h", "--help"):
        from splitter_nsp.ui.app import run
        return run()

    p = argparse.ArgumentParser(prog="splitter_nsp", description="Split NSP files for FAT32")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split", help="split a file from the command line")
    s.add_argument("source", type=Path)
    s.add_argument("dest_dir", type=Path)
    i = sub.add_parser("info", help="show the Title ID of a file")
    i.add_argument("files", nargs="+", type=Path)
    a = sub.add_parser("set-archive", help="(internal) set the archive bit on FAT32")
    a.add_argument("device")
    a.add_argument("paths", nargs="+")
    args = p.parse_args(argv)

    if args.cmd == "info":
        from splitter_nsp.inspector import inspect
        for f in args.files:
            info = inspect(f)
            print(f"{f.name}: {info.title_id} ({info.kind}) base={info.base_title_id}")
        return 0

    if args.cmd == "set-archive":
        from splitter_nsp.archive_bit import set_archive_on_device
        msgs = set_archive_on_device(args.device, args.paths)
        print("\n".join(msgs))
        return 1 if any(m.startswith("ERR") for m in msgs) else 0

    if args.cmd == "split":
        from splitter_nsp import engine
        size = args.source.stat().st_size
        split = engine.needs_split(size)
        done = [0]

        def progress(n):
            done[0] += n
            print(f"\r{done[0] * 100 // size:3d}%", end="", flush=True)

        dest = args.dest_dir / args.source.name
        engine.process(args.source, dest, split, progress, lambda: False)
        engine.clean_appledouble(args.dest_dir)
        if split:
            engine.clean_appledouble(dest)
        what = f"split into {engine.part_count(size)} parts" if split else "copied"
        print(f"\nDone: {dest} ({what})")
        return 0
    return 1
