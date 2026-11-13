"""Build a standalone app with PyInstaller.

    python scripts/build.py

macOS   -> dist/SplitterNSP-macOS-<arch>.dmg   (SplitterNSP.app inside)
Windows -> dist/SplitterNSP-Windows-x64.exe    (single portable file)
Linux   -> dist/SplitterNSP-Linux-x64          (single file)
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from splitter_nsp import __version__  # noqa: E402

NAME = "SplitterNSP"


def run(*cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=ROOT)


def main() -> None:
    dist, build = ROOT / "dist", ROOT / "build"
    shutil.rmtree(dist, ignore_errors=True)
    shutil.rmtree(build, ignore_errors=True)
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
            "--name", NAME, "--distpath", dist, "--workpath", build, "--specpath", build]
    for mod in ("tkinter", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick",
                "PySide6.QtPdf", "PySide6.QtWebEngineCore", "PySide6.QtMultimedia"):
        args += ["--exclude-module", mod]

    if sys.platform == "darwin":
        arch = platform.machine()
        run(*args, "--icon", ROOT / "assets/icon.icns",
            "--osx-bundle-identifier", "io.github.hentoo99.splitternsp", ROOT / "SplitterNSP.py")
        app = dist / f"{NAME}.app"
        plist = app / "Contents/Info.plist"
        run("plutil", "-replace", "CFBundleShortVersionString", "-string", __version__, plist)
        run("plutil", "-replace", "CFBundleVersion", "-string", __version__, plist)
        run("plutil", "-replace", "NSHumanReadableCopyright", "-string", "MIT License", plist)
        run("codesign", "--force", "--deep", "--sign", "-", app)
        stage = build / "dmg"
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True)
        run("ditto", app, stage / f"{NAME}.app")
        (stage / "Applications").symlink_to("/Applications")
        out = dist / f"{NAME}-macOS-{'AppleSilicon' if arch == 'arm64' else 'Intel'}.dmg"
        run("hdiutil", "create", "-volname", NAME, "-srcfolder", stage, "-ov", "-format", "UDZO", out)
    elif sys.platform == "win32":
        run(*args, "--onefile", "--icon", ROOT / "assets/icon.ico", ROOT / "SplitterNSP.py")
        (dist / f"{NAME}.exe").rename(dist / f"{NAME}-Windows-x64.exe")
    else:
        run(*args, "--onefile", ROOT / "SplitterNSP.py")
        (dist / NAME).rename(dist / f"{NAME}-Linux-x64")
    print("\nBuilt:", *[p.name for p in dist.iterdir()], sep="\n  ")


if __name__ == "__main__":
    main()
