"""Reads basic information from NSP/NSZ/XCI files without decrypting them."""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

SUPPORTED_EXTENSIONS = {".nsp", ".nsz", ".xci", ".xcz"}

KIND_BASE = "Game"
KIND_UPDATE = "Update"
KIND_DLC = "DLC"
KIND_UNKNOWN = "Unknown"


@dataclass
class ContainerInfo:
    title_id: Optional[str] = None
    version: Optional[str] = None
    kind: str = KIND_UNKNOWN

    @property
    def base_title_id(self) -> Optional[str]:
        """Title ID of the base game (for updates/DLC), used for the name and cover art."""
        if not self.title_id:
            return None
        value = int(self.title_id, 16) & ~0xFFF
        if self.kind == KIND_DLC:
            value ^= 0x1000
        return f"{value:016X}"


def pfs0_entries(path: Path) -> Optional[List[tuple]]:
    """Return [(name, absolute_offset, size)] for a PFS0 container (NSP)."""
    try:
        with open(path, "rb") as f:
            header = f.read(16)
            if len(header) != 16 or header[:4] != b"PFS0":
                return None
            count, str_size = struct.unpack_from("<II", header, 4)
            if not (0 < count < 4096) or str_size > 1 << 20:
                return None
            table = f.read(count * 0x18 + str_size)
            if len(table) != count * 0x18 + str_size:
                return None
    except OSError:
        return None
    strings = table[count * 0x18:]
    data_start = 16 + count * 0x18 + str_size
    entries = []
    for i in range(count):
        offset, size, name_off = struct.unpack_from("<QQI", table, i * 0x18)
        if name_off >= len(strings):
            continue
        end = strings.find(b"\0", name_off)
        name = strings[name_off:end if end >= 0 else None].decode("utf-8", "replace")
        entries.append((name, data_start + offset, size))
    return entries


def _first(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def inspect(path: Path) -> ContainerInfo:
    info = ContainerInfo()
    entries = pfs0_entries(path)
    if entries:
        # The .tik ticket is named after the Rights ID: the first 16 characters are the Title ID.
        tik = next((e for e in entries if e[0].lower().endswith(".tik")), None)
        if tik and len(tik[0]) >= 20:
            info.title_id = tik[0][:16].upper()
        else:
            xml = next((e for e in entries if e[0].lower().endswith(".cnmt.xml")), None)
            if xml and xml[2] < 1 << 20:
                try:
                    with open(path, "rb") as f:
                        f.seek(xml[1])
                        text = f.read(xml[2]).decode("utf-8", "replace")
                    tid = _first(r"<Id>0x([0-9A-Fa-f]{16})</Id>", text)
                    info.title_id = tid.upper() if tid else None
                except OSError:
                    pass

    name = path.name
    if not info.title_id:
        tid = _first(r"\[([0-9A-Fa-f]{16})\]", name) or _first(r"\b(01[0-9A-Fa-f]{14})\b", name)
        info.title_id = tid.upper() if tid else None
    info.version = _first(r"\[v(\d+)\]", name)

    if info.title_id:
        value = int(info.title_id, 16)
        low = value & 0xFFF
        if low == 0x800:
            info.kind = KIND_UPDATE
        elif low == 0 and not value & 0x1000:
            info.kind = KIND_BASE
        else:
            info.kind = KIND_DLC
    return info


def pretty_name(filename: str) -> str:
    """Readable name derived from the file name when there is no online metadata."""
    s = Path(filename).stem
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = re.sub(r"\([^)]*\)", "", s)
    s = s.replace("_", " ").strip(" -")
    return s or filename
