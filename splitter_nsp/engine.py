"""Splitting/copying files into the "folder with archive bit" format.

This is the format recognized by Atmosphère, DBI, Tinfoil, Awoo...:
a folder named like the file (e.g. ``Game.nsp/``) that contains the parts
``00``, ``01``, ``02``... of 0xFFFF0000 bytes (4 GiB - 64 KiB) each,
exactly like splitNSP.py does.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Callable

PART_SIZE = 0xFFFF0000
FAT32_MAX_FILE = 0xFFFFFFFF
CHUNK = 8 * 1024 * 1024


class Cancelled(Exception):
    pass


def needs_split(size: int) -> bool:
    return size > FAT32_MAX_FILE


def part_count(size: int) -> int:
    return max(1, -(-size // PART_SIZE))


def process(source: Path, destination: Path, split: bool,
            progress: Callable[[int], None], cancelled: Callable[[], bool]) -> None:
    """Split ``source`` into ``destination`` (a folder) or copy it as is."""
    if destination.is_dir():
        shutil.rmtree(destination)
    elif destination.exists():
        destination.unlink()

    try:
        with open(source, "rb", buffering=0) as src:
            if split:
                destination.mkdir(parents=True)
                index = 0
                while True:
                    part = destination / f"{index:02d}"
                    written = _copy(src, part, PART_SIZE, progress, cancelled)
                    if written == 0:
                        part.unlink()
                        break
                    index += 1
                    if written < PART_SIZE:
                        break
            else:
                _copy(src, destination, None, progress, cancelled)
    except BaseException:
        if destination.is_dir():
            shutil.rmtree(destination, ignore_errors=True)
        elif destination.exists():
            destination.unlink()
        raise


def _copy(src, dest: Path, limit, progress, cancelled) -> int:
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        if sys.platform == "darwin":
            # F_NOCACHE: progress follows the real speed of the SD card.
            import fcntl
            fcntl.fcntl(fd, getattr(fcntl, "F_NOCACHE", 48), 1)
        written = 0
        while limit is None or written < limit:
            if cancelled():
                raise Cancelled()
            want = CHUNK if limit is None else min(CHUNK, limit - written)
            data = src.read(want)
            if not data:
                break
            view = memoryview(data)
            while view:
                n = os.write(fd, view)
                view = view[n:]
            written += len(data)
            progress(len(data))
        os.fsync(fd)
        return written
    finally:
        os.close(fd)


def clean_appledouble(folder: Path) -> None:
    """On FAT32, macOS stores extended attributes (e.g. com.apple.provenance, which can't
    be removed) in hidden "._name" files: they confuse the console installers, so we
    delete them once the job is done."""
    if sys.platform != "darwin" or not folder.is_dir():
        return
    for p in folder.iterdir():
        if p.name.startswith("._"):
            try:
                p.unlink()
            except OSError:
                pass
