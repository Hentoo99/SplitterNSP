"""Setting the "archive" bit on split folders.

The Switch (Atmosphère, DBI, Tinfoil...) treats a ``Game.nsp`` folder as a single
file only if it has the FAT "archive" attribute (0x20).

* Windows: ``attrib +A`` is enough.
* Linux:   ``fatattr +a`` if installed.
* macOS:   the system doesn't allow setting it on folders, so we edit the
           attribute byte directly in the FAT32 directory entry while the card
           is unmounted (administrator privileges are required).
"""
from __future__ import annotations

import os
import shlex
import shutil
import struct
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

ATTR_DIRECTORY = 0x10
ATTR_ARCHIVE = 0x20
ATTR_LFN = 0x0F
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FatError(Exception):
    pass


def _key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _lfn_checksum(short: bytes) -> int:
    s = 0
    for c in short:
        s = (((s & 1) << 7) + (s >> 1) + c) & 0xFF
    return s


class Fat32Volume:
    """Minimal read/write access to a FAT32 file system (device or image)."""

    def __init__(self, path: str):
        self.fd = os.open(path, os.O_RDWR)
        boot = os.pread(self.fd, 4096, 0)
        if len(boot) < 512 or boot[510:512] != b"\x55\xAA":
            raise FatError("Invalid boot sector")
        bps, spc, reserved, nfats = struct.unpack_from("<HBHB", boot, 11)
        fat16_size = struct.unpack_from("<H", boot, 22)[0]
        fat_size, self.root_cluster = struct.unpack_from("<I4xI", boot, 36)
        if fat16_size != 0 or boot[82:87] != b"FAT32" or bps not in (512, 1024, 2048, 4096):
            raise FatError("The volume is not FAT32")
        self.bps = bps
        self.cluster_size = bps * spc
        self.fat_offset = reserved * bps
        self.data_offset = (reserved + nfats * fat_size) * bps

    def close(self):
        os.close(self.fd)

    def _read(self, offset: int, length: int) -> bytes:
        start = offset - offset % self.bps
        end = -(-(offset + length) // self.bps) * self.bps
        data = os.pread(self.fd, end - start, start)
        return data[offset - start: offset - start + length]

    def _next_cluster(self, cluster: int) -> int:
        return struct.unpack("<I", self._read(self.fat_offset + cluster * 4, 4))[0] & 0x0FFFFFFF

    def _cluster_chain(self, cluster: int) -> Iterator[int]:
        seen = set()
        while 2 <= cluster < 0x0FFFFFF7 and cluster not in seen:
            seen.add(cluster)
            yield cluster
            cluster = self._next_cluster(cluster)

    def _entries(self, cluster: int) -> Iterator[Tuple[str, int, int, int]]:
        """(name, attributes, first cluster, absolute offset of the entry)"""
        lfn = {}
        for c in self._cluster_chain(cluster):
            base = self.data_offset + (c - 2) * self.cluster_size
            data = self._read(base, self.cluster_size)
            for i in range(0, self.cluster_size, 32):
                e = data[i:i + 32]
                if e[0] == 0x00:
                    return
                if e[0] == 0xE5:
                    lfn.clear()
                    continue
                attr = e[11]
                if attr == ATTR_LFN:
                    seq = e[0] & 0x1F
                    raw = e[1:11] + e[14:26] + e[28:32]
                    lfn[seq] = (raw.decode("utf-16-le", "replace"), e[13])
                    continue
                short = e[0:11]
                name = None
                if lfn:
                    chk = _lfn_checksum(short)
                    if all(v[1] == chk for v in lfn.values()):
                        name = "".join(lfn[k][0] for k in sorted(lfn))
                        name = name.split("\x00")[0].replace("￿", "")
                    lfn.clear()
                if name is None:
                    base_n = short[:8].decode("latin-1").rstrip()
                    ext = short[8:].decode("latin-1").rstrip()
                    if e[12] & 0x08:
                        base_n = base_n.lower()
                    if e[12] & 0x10:
                        ext = ext.lower()
                    name = base_n + ("." + ext if ext else "")
                start = (struct.unpack_from("<H", e, 20)[0] << 16) | struct.unpack_from("<H", e, 26)[0]
                yield name, attr, start, base + i

    def find(self, rel_path: str) -> Tuple[int, int]:
        """Return (attributes, entry offset) for a path relative to the root."""
        parts = [p for p in Path(rel_path).parts if p not in ("/", "\\")]
        if not parts:
            raise FatError("Empty path")
        cluster = self.root_cluster
        for depth, part in enumerate(parts):
            for name, attr, start, offset in self._entries(cluster):
                if attr & 0x08:  # volume label
                    continue
                if _key(name) == _key(part):
                    if depth == len(parts) - 1:
                        return attr, offset
                    if not attr & ATTR_DIRECTORY:
                        raise FatError(f"{part} is not a folder")
                    cluster = start or self.root_cluster
                    break
            else:
                raise FatError(f"'{part}' not found")
        raise FatError("Path not found")

    def set_archive(self, rel_path: str) -> bool:
        """Set the archive bit. Returns False if it was already set."""
        attr, offset = self.find(rel_path)
        if attr & ATTR_ARCHIVE:
            return False
        sector = offset - offset % self.bps
        data = bytearray(os.pread(self.fd, self.bps, sector))
        pos = offset - sector + 11
        if data[pos] != attr:
            raise FatError("Inconsistent directory entry, nothing was changed")
        data[pos] = attr | ATTR_ARCHIVE
        os.pwrite(self.fd, bytes(data), sector)
        os.fsync(self.fd)
        return True


def set_archive_on_device(device: str, rel_paths: List[str]) -> List[str]:
    """Used by the process with administrator privileges. Returns the messages."""
    vol = Fat32Volume(device)
    msgs = []
    try:
        for rel in rel_paths:
            try:
                changed = vol.set_archive(rel)
                msgs.append(f"OK {rel}" if changed else f"ALREADY {rel}")
            except FatError as e:
                msgs.append(f"ERR {rel}: {e}")
    finally:
        vol.close()
    return msgs


# --------------------------------------------------------------------------- #
#  Per-platform dispatch
# --------------------------------------------------------------------------- #

def apply(folders: List[Path], mount_point: str, device: str) -> Tuple[bool, str]:
    """Set the archive bit on the given folders. Returns (ok, message)."""
    if not folders:
        return True, "No folders to fix."
    if os.name == "nt":
        errors = []
        for f in folders:
            r = subprocess.run(["attrib", "+A", str(f)], capture_output=True, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0:
                errors.append(f"{f.name}: {r.stderr.strip() or r.stdout.strip()}")
        return (not errors), ("\n".join(errors) or "Archive bit set.")
    if sys.platform == "darwin":
        return _apply_macos(folders, mount_point, device)
    if shutil.which("fatattr"):
        r = subprocess.run(["fatattr", "+a"] + [str(f) for f in folders],
                           capture_output=True, text=True)
        return r.returncode == 0, (r.stderr.strip() or "Archive bit set.")
    return False, "Install 'fatattr' (e.g. sudo apt install fatattr) or use Hekate."


def _apply_macos(folders: List[Path], mount_point: str, device: str) -> Tuple[bool, str]:
    raw = device.replace("/dev/disk", "/dev/rdisk", 1)
    rel = [str(Path(f).resolve().relative_to(Path(mount_point).resolve())) for f in folders]

    r = subprocess.run(["diskutil", "unmount", mount_point], capture_output=True, text=True)
    if r.returncode != 0:
        return False, ("Couldn't unmount the card (is an app using it?).\n"
                       + (r.stderr.strip() or r.stdout.strip()))
    try:
        if os.access(raw, os.R_OK | os.W_OK):
            # device already writable (e.g. a disk image): no password needed
            try:
                msgs = set_archive_on_device(raw, rel)
            except (OSError, FatError) as e:
                return False, str(e)
            errors = [m for m in msgs if m.startswith("ERR")]
            return (not errors), ("\n".join(errors) if errors else "Archive bit set.")
        if getattr(sys, "frozen", False):  # standalone app built with PyInstaller
            helper = [sys.executable, "set-archive", raw]
        else:
            helper = ["env", f"PYTHONPATH={PROJECT_ROOT}", sys.executable, "-m",
                      "splitter_nsp", "set-archive", raw]
        cmd = " ".join(shlex.quote(x) for x in helper + rel)
        script = cmd.replace("\\", "\\\\").replace('"', '\\"')
        prompt = "SplitterNSP needs to set the archive bit on your game folders."
        r = subprocess.run(
            ["osascript", "-e",
             f'do shell script "{script}" with prompt "{prompt}" with administrator privileges'],
            capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            if "-128" in out:
                return False, "Cancelled: no password was entered."
            return False, out or "Unknown error."
        errors = [l for l in out.splitlines() if l.startswith("ERR")]
        return (not errors), ("\n".join(errors) if errors else "Archive bit set.")
    finally:
        subprocess.run(["diskutil", "mount", device], capture_output=True, text=True)
