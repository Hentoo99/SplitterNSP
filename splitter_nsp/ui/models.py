"""Data shared by the UI, and background workers."""
from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, QRunnable, QThread, Signal
from PySide6.QtGui import QPixmap

from .. import archive_bit, engine, metadata
from ..inspector import ContainerInfo, inspect, pretty_name
from ..volumes import Volume, human


@dataclass(eq=False)
class GameItem:
    path: Path
    size: int
    info: ContainerInfo
    name: str
    publisher: str = ""
    icon: Optional[QPixmap] = None
    banner: Optional[QPixmap] = None
    status: str = "pending"  # pending, running, done, error
    error: str = ""

    @classmethod
    def from_path(cls, path: Path) -> "GameItem":
        return cls(path=path, size=path.stat().st_size, info=inspect(path),
                   name=pretty_name(path.name))

    @property
    def split(self) -> bool:
        return engine.needs_split(self.size)

    @property
    def parts(self) -> int:
        return engine.part_count(self.size) if self.split else 1

    @property
    def size_label(self) -> str:
        return human(self.size)

    @property
    def target_name(self) -> str:
        return safe_fat_name(self.path.name)


def safe_fat_name(name: str) -> str:
    """FAT32 doesn't accept some characters in names."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name.rstrip(" .") or "game.nsp"


@dataclass
class Destination:
    folder: Path            # base folder (card root or chosen folder)
    volume: Optional[Volume]
    subfolder: str = ""
    custom: bool = False

    @property
    def root(self) -> Path:
        sub = self.subfolder.strip().strip("/\\")
        return self.folder / sub if sub else self.folder

    @property
    def is_fat(self) -> bool:
        return bool(self.volume and self.volume.is_fat)


# --------------------------------------------------------------------------- #
#  Background metadata
# --------------------------------------------------------------------------- #

class MetaBus(QObject):
    meta = Signal(object, object)          # item, dict
    image = Signal(object, str, object)    # item, kind, bytes


class MetaTask(QRunnable):
    def __init__(self, item: GameItem, bus: MetaBus):
        super().__init__()
        self.item = item
        self.bus = bus

    def run(self):
        tid = self.item.info.base_title_id
        if not tid:
            return
        meta = metadata.fetch_metadata(tid)
        if meta:
            self.bus.meta.emit(self.item, meta)
        for kind in ("icon", "banner"):
            data = metadata.fetch_image(tid, kind)
            if data:
                self.bus.image.emit(self.item, kind, data)


# --------------------------------------------------------------------------- #
#  Background splitting
# --------------------------------------------------------------------------- #

class SplitWorker(QThread):
    item_started = Signal(int)
    progress = Signal(object, int, object)        # total bytes, index, game bytes
    item_finished = Signal(int, bool, str)
    phase = Signal(str)
    done = Signal(bool, bool, str)                # cancelled, archive bit ok, message

    def __init__(self, items: List[GameItem], dest: Destination, fix_archive: bool,
                 eject: bool):
        super().__init__()
        self.items = items
        self.dest = dest
        self.fix_archive = fix_archive
        self.eject = eject
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        root = self.dest.root
        total = 0
        split_folders = []
        cancelled = False
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            for i in range(len(self.items)):
                self.item_finished.emit(i, False, f"Couldn't create the folder: {e}")
            self.done.emit(False, False, "")
            return

        for i, item in enumerate(self.items):
            if self._cancel:
                cancelled = True
                break
            self.item_started.emit(i)
            done_item = [0]
            last = [0.0]

            def progress(n, i=i, done_item=done_item, last=last):
                nonlocal total
                total += n
                done_item[0] += n
                now = time.monotonic()
                if now - last[0] > 0.08:
                    last[0] = now
                    self.progress.emit(total, i, done_item[0])

            target = root / item.target_name
            try:
                engine.process(item.path, target, item.split, progress, lambda: self._cancel)
                self.progress.emit(total, i, done_item[0])
                if item.split:
                    split_folders.append(target)
                self.item_finished.emit(i, True, "")
            except engine.Cancelled:
                cancelled = True
                self.item_finished.emit(i, False, "Cancelled")
                break
            except OSError as e:
                msg = e.strerror or str(e)
                if getattr(e, "errno", None) == 28:
                    msg = "The destination is out of space"
                self.item_finished.emit(i, False, msg)
            except Exception as e:  # noqa: BLE001
                self.item_finished.emit(i, False, str(e))

        # Clean up the "._" files created by macOS
        self.phase.emit("Cleaning up hidden macOS files…")
        mount = Path(self.dest.volume.mount_point) if self.dest.volume else None
        folder = root
        while True:
            engine.clean_appledouble(folder)
            if mount is None or folder == mount or folder.parent == folder:
                break
            folder = folder.parent
        for f in split_folders:
            engine.clean_appledouble(f)

        arch_ok, arch_msg = True, ""
        if self.fix_archive and split_folders and self.dest.volume:
            self.phase.emit("Setting the archive bit on the folders…")
            arch_ok, arch_msg = archive_bit.apply(split_folders, self.dest.volume.mount_point,
                                                  self.dest.volume.device)
        if self.eject and self.dest.volume and sys.platform == "darwin" and not cancelled:
            self.phase.emit("Ejecting the card…")
            subprocess.run(["diskutil", "eject", self.dest.volume.mount_point],
                           capture_output=True)
        self.done.emit(cancelled, arch_ok, arch_msg)
