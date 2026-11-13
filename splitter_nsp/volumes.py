"""Cross-platform list of external drives (SD cards) with their file system type."""
from __future__ import annotations

import os
import re
import shutil
import string
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Volume:
    name: str
    mount_point: str
    device: str
    fs_type: str  # normalized: fat32, exfat, ntfs, apfs, ...
    total: int
    free: int
    removable: bool = True

    @property
    def is_fat(self) -> bool:
        return self.fs_type in ("fat32", "fat16", "fat")

    @property
    def format_label(self) -> str:
        return {"fat32": "FAT32", "fat16": "FAT16", "fat": "FAT", "exfat": "exFAT",
                "ntfs": "NTFS", "apfs": "APFS", "hfs": "Mac OS Extended"}.get(self.fs_type,
                                                                              self.fs_type.upper())


def _norm_fs(fs: str) -> str:
    fs = fs.lower()
    if fs in ("msdos", "vfat", "fat32", "msdosfs"):
        return "fat32"
    if fs in ("fat", "fat16", "fat12"):
        return "fat16"
    if fs in ("fuseblk",):
        return "ntfs"
    return fs


def _usage(mount: str):
    try:
        u = shutil.disk_usage(mount)
        return u.total, u.free
    except OSError:
        return 0, 0


def _unix_mounts() -> List[tuple]:
    """[(device, mount_point, fs_type)]"""
    result = []
    if sys.platform == "darwin":
        out = subprocess.run(["/sbin/mount"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            m = re.match(r"^(\S+) on (.+) \(([^,)]+)", line)
            if m:
                result.append((m.group(1), m.group(2), m.group(3)))
    else:
        try:
            with open("/proc/mounts") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3:
                        mp = parts[1].replace("\\040", " ")
                        result.append((parts[0], mp, parts[2]))
        except OSError:
            pass
    return result


def _windows_volumes(include_all: bool = False) -> List[Volume]:
    import ctypes
    k32 = ctypes.windll.kernel32
    vols = []
    mask = k32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not mask & (1 << i):
            continue
        root = f"{letter}:\\"
        dtype = k32.GetDriveTypeW(root)
        removable = dtype == 2  # DRIVE_REMOVABLE
        if not include_all and (not removable and not (dtype == 3 and letter != "C")):
            continue
        label = ctypes.create_unicode_buffer(261)
        fs = ctypes.create_unicode_buffer(261)
        if not k32.GetVolumeInformationW(root, label, 261, None, None, None, fs, 261):
            continue
        total, free = _usage(root)
        vols.append(Volume(label.value or f"Drive {letter}:", root, root, _norm_fs(fs.value),
                           total, free, removable))
    return vols


def external_volumes() -> List[Volume]:
    """Mounted external/removable volumes, FAT32 first."""
    if os.name == "nt":
        vols = _windows_volumes()
    else:
        vols = []
        for dev, mp, fs in _unix_mounts():
            if not dev.startswith("/dev/"):
                continue
            if sys.platform == "darwin":
                if not mp.startswith("/Volumes/"):
                    continue
            elif not mp.startswith(("/media/", "/run/media/", "/mnt/")):
                continue
            total, free = _usage(mp)
            vols.append(Volume(Path(mp).name, mp, dev, _norm_fs(fs), total, free))
    vols.sort(key=lambda v: (not v.is_fat, v.name.lower()))
    return vols


def volume_for_path(path: Path) -> Optional[Volume]:
    """The volume that contains any given folder."""
    path = Path(path).resolve()
    if os.name == "nt":
        drive = path.drive.upper() + "\\"
        for v in _windows_volumes(include_all=True):
            if v.mount_point.upper() == drive:
                return v
        return None
    best = None
    for dev, mp, fs in _unix_mounts():
        if str(path) == mp or str(path).startswith(mp.rstrip("/") + "/"):
            if best is None or len(mp) > len(best[1]):
                best = (dev, mp, fs)
    if not best:
        return None
    total, free = _usage(best[1])
    name = Path(best[1]).name or "System disk"
    return Volume(name, best[1], best[0], _norm_fs(best[2]), total, free,
                  removable=best[1] != "/")


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"
