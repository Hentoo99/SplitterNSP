"""Generate app icons (png/icns/ico) and the README hero banner.

Usage:  python scripts/make_assets.py
Needs the screenshots in docs/ (docs/1_games.png, docs/4_progress.png).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QImage, QLinearGradient,  # noqa: E402
                           QPainter, QPainterPath, QPen, QRadialGradient, QTransform)

from splitter_nsp.ui import theme as T  # noqa: E402


def icons(out: Path) -> None:
    out.mkdir(exist_ok=True)
    big = T.app_icon_pixmap(1024).toImage()
    big.save(str(out / "icon.png"))
    big.save(str(out / "icon.icns"))
    big.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(str(out / "icon.ico"))


def _shot(p: QPainter, img: QImage, rect: QRectF, angle: float) -> None:
    p.save()
    p.translate(rect.center())
    p.rotate(angle)
    r = QRectF(-rect.width() / 2, -rect.height() / 2, rect.width(), rect.height())
    for i in range(18, 0, -2):  # soft shadow
        sh = QPainterPath()
        sh.addRoundedRect(r.adjusted(-i, -i + 18, i, i + 18), 18 + i, 18 + i)
        p.fillPath(sh, QColor(0, 0, 0, 10))
    path = QPainterPath()
    path.addRoundedRect(r, 16, 16)
    p.setClipPath(path)
    p.drawImage(r, img)
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
    p.drawPath(path)
    p.restore()


def hero(out: Path) -> None:
    W, H = 1600, 720
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(T.BG))
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    for c, pos, rad in ((T.RED, QPointF(180, 120), 620), (T.BLUE, QPointF(1450, 650), 720),
                        (T.PURPLE, QPointF(900, 0), 420)):
        g = QRadialGradient(pos, rad)
        col = QColor(c)
        col.setAlpha(70)
        g.setColorAt(0, col)
        col.setAlpha(0)
        g.setColorAt(1, col)
        p.fillRect(img.rect(), g)
    # dotted grid
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 14))
    for x in range(20, W, 32):
        for y in range(20, H, 32):
            p.drawEllipse(QPointF(x, y), 1.2, 1.2)

    shots = ROOT / "docs"
    back = QImage(str(shots / "4_progress.png"))
    front = QImage(str(shots / "1_games.png"))
    if not back.isNull():
        _shot(p, back, QRectF(930, 70, 640, 423), 5)
    if not front.isNull():
        _shot(p, front, QRectF(800, 250, 700, 463), -3)

    icon = T.app_icon_pixmap(512)
    p.drawPixmap(QRectF(90, 120, 132, 132), icon, QRectF(icon.rect()))

    f = QFont("Helvetica Neue")
    f.setPixelSize(92)
    f.setWeight(QFont.Black)
    p.setFont(f)
    p.setPen(QColor(T.TEXT))
    p.drawText(QRectF(90, 270, 760, 110), Qt.AlignLeft | Qt.AlignVCenter, "Splitter")
    w = p.fontMetrics().horizontalAdvance("Splitter")
    g = QLinearGradient(90 + w, 0, 90 + w + 230, 0)
    g.setColorAt(0, QColor(T.RED))
    g.setColorAt(1, QColor(T.BLUE))
    p.setPen(QPen(g, 1))
    path = QPainterPath()
    path.addText(QPointF(90 + w + 4, 357), f, "NSP")
    p.fillPath(path, g)

    f.setPixelSize(34)
    f.setWeight(QFont.Bold)
    p.setFont(f)
    p.setPen(QColor(T.TEXT))
    p.drawText(QRectF(92, 395, 720, 50), Qt.AlignLeft, "Huge Switch games. FAT32 SD cards.")
    p.setPen(QColor(T.MUTED))
    f.setWeight(QFont.Normal)
    f.setPixelSize(26)
    p.setFont(f)
    p.drawText(QRectF(92, 448, 700, 120), Qt.AlignLeft | Qt.TextWordWrap,
               "Split NSP / NSZ / XCI over 4 GB in a few clicks,\nwith cover art and the archive bit set for you.")

    # pills
    f.setPixelSize(19)
    f.setWeight(QFont.DemiBold)
    p.setFont(f)
    x = 92
    for text in ("macOS", "Windows", "Linux", "Drag & drop", "Free & open source"):
        tw = p.fontMetrics().horizontalAdvance(text) + 34
        r = QRectF(x, 570, tw, 40)
        pill = QPainterPath()
        pill.addRoundedRect(r, 20, 20)
        p.fillPath(pill, QColor(255, 255, 255, 16))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawPath(pill)
        p.setPen(QColor(T.TEXT))
        p.drawText(r, Qt.AlignCenter, text)
        x += tw + 12
    p.end()
    img.save(str(out / "hero.png"))


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    icons(ROOT / "assets")
    hero(ROOT / "docs")
    print("assets written")
