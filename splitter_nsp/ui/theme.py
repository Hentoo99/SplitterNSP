"""Colors, stylesheet and small drawing helpers."""
from __future__ import annotations

import hashlib

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap)

BG = "#0c0e13"
SIDEBAR = "#10131a"
SURFACE = "#161a23"
SURFACE_2 = "#1d222d"
SURFACE_3 = "#262c39"
BORDER = "#2a3140"
TEXT = "#eef1f7"
MUTED = "#8b93a7"
DIM = "#5d6578"
RED = "#ff3d63"
BLUE = "#1fb6ff"
PURPLE = "#8b5cf6"
GREEN = "#2ed38a"
AMBER = "#ffb547"

QSS = f"""
QWidget {{ color: {TEXT}; font-size: 13px; }}
QMainWindow, #root {{ background: {BG}; }}
#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
#footer {{ background: transparent; border-top: 1px solid {BORDER}; }}
QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: 28px; font-weight: 800; }}
QLabel#h2 {{ font-size: 18px; font-weight: 700; }}
QLabel#sub {{ color: {MUTED}; font-size: 14px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#dim {{ color: {DIM}; font-size: 12px; }}
QLabel#cardTitle {{ font-size: 17px; font-weight: 700; }}
QLabel#cardSub {{ color: {MUTED}; font-size: 12px; }}
QLabel#statValue {{ font-size: 24px; font-weight: 800; }}
QLabel#statLabel {{ color: {MUTED}; font-size: 12px; }}
QLabel#chip {{ border-radius: 9px; padding: 3px 9px; font-size: 11px; font-weight: 700;
               background: {SURFACE_3}; color: {MUTED}; }}
QLabel#chip[tone="red"] {{ background: rgba(255,61,99,0.16); color: #ff7d97; }}
QLabel#chip[tone="blue"] {{ background: rgba(31,182,255,0.15); color: #6fd0ff; }}
QLabel#chip[tone="green"] {{ background: rgba(46,211,138,0.15); color: #5fe3a8; }}
QLabel#chip[tone="amber"] {{ background: rgba(255,181,71,0.15); color: #ffc874; }}
QLabel#chip[tone="purple"] {{ background: rgba(139,92,246,0.18); color: #b39bff; }}
QFrame#panel {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 16px; }}
QFrame#notice {{ background: rgba(31,182,255,0.08); border: 1px solid rgba(31,182,255,0.30);
                 border-radius: 12px; }}
QFrame#notice[tone="amber"] {{ background: rgba(255,181,71,0.08); border-color: rgba(255,181,71,0.35); }}
QFrame#notice[tone="red"] {{ background: rgba(255,61,99,0.08); border-color: rgba(255,61,99,0.40); }}
QFrame#notice[tone="green"] {{ background: rgba(46,211,138,0.08); border-color: rgba(46,211,138,0.35); }}
QPushButton {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px;
               padding: 9px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {SURFACE_3}; border-color: #3a4357; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {DIM}; }}
QPushButton#ghost {{ background: transparent; border: none; color: {MUTED}; padding: 6px 10px; }}
QPushButton#ghost:hover {{ color: {TEXT}; background: {SURFACE_2}; }}
QPushButton#close {{ background: rgba(0,0,0,0.35); border: none; border-radius: 14px; padding: 0;
                     color: {MUTED}; font-size: 15px; font-weight: 700; }}
QPushButton#close:hover {{ background: {RED}; color: white; }}
QLineEdit {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px;
             padding: 8px 12px; selection-background-color: {BLUE}; }}
QLineEdit:focus {{ border-color: {BLUE}; }}
QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 6px; border: 1px solid #3a4357;
                        background: {SURFACE_2}; }}
QCheckBox::indicator:checked {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {RED}, stop:1 {BLUE});
                                border: none; image: url("{{CHECK}}"); }}
QCheckBox:disabled {{ color: {DIM}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #3a4357; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QProgressBar {{ background: {SURFACE_3}; border: none; border-radius: 5px; height: 10px;
                text-align: center; color: transparent; }}
QProgressBar::chunk {{ border-radius: 5px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {RED}, stop:1 {BLUE}); }}
QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; }}
"""


def accent_gradient(rect: QRectF, a: str = RED, b: str = BLUE) -> QLinearGradient:
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    g.setColorAt(0, QColor(a))
    g.setColorAt(1, QColor(b))
    return g


def color_pair(seed: str):
    """Two vivid, stable colors derived from a string (for placeholders)."""
    h = hashlib.md5(seed.encode("utf-8")).digest()
    c1 = QColor.fromHsv(h[0] * 360 // 256, 170, 235)
    c2 = QColor.fromHsv((h[0] * 360 // 256 + 50 + h[1] % 60) % 360, 190, 170)
    return c1, c2


def placeholder_icon(name: str, size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    c1, c2 = color_pair(name)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, c1)
    g.setColorAt(1, c2)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), size * 0.2, size * 0.2)
    p.fillPath(path, QBrush(g))
    words = [w for w in name.replace("-", " ").split() if w[:1].isalnum()]
    letters = "".join(w[0] for w in words[:2]).upper() or "?"
    f = QFont()
    f.setPixelSize(int(size * 0.38))
    f.setWeight(QFont.Black)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255, 235))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, letters)
    p.end()
    return pix


def rounded(pix: QPixmap, size: int, radius_ratio: float = 0.2) -> QPixmap:
    dpr = 2.0
    out = QPixmap(int(size * dpr), int(size * dpr))
    out.setDevicePixelRatio(dpr)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), size * radius_ratio, size * radius_ratio)
    p.setClipPath(path)
    p.drawPixmap(QRectF(0, 0, size, size), pix, QRectF(pix.rect()))
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 30), 1))
    p.drawPath(path)
    p.end()
    return out


def app_icon_pixmap(size: int = 512) -> QPixmap:
    """App icon: two cartridge "halves" separated by a glowing cut."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88), s * 0.22, s * 0.22)
    g = QLinearGradient(0, 0, s, s)
    g.setColorAt(0, QColor("#1b2030"))
    g.setColorAt(1, QColor("#0c0e13"))
    p.fillPath(bg, g)
    left = QPainterPath()
    left.addRoundedRect(QRectF(s * 0.22, s * 0.24, s * 0.25, s * 0.52), s * 0.07, s * 0.07)
    right = QPainterPath()
    right.addRoundedRect(QRectF(s * 0.53, s * 0.24, s * 0.25, s * 0.52), s * 0.07, s * 0.07)
    p.fillPath(left, QColor(RED))
    p.fillPath(right, QColor(BLUE))
    pen = QPen(QColor(255, 255, 255, 220), s * 0.018, Qt.DashLine, Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(s * 0.5, s * 0.18), QPointF(s * 0.5, s * 0.82))
    p.end()
    return pix


def build_stylesheet() -> str:
    """Stylesheet, with the checkbox tick icon generated on the fly."""
    from pathlib import Path
    import tempfile
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">'
           '<path d="M5 10.5l3.2 3.2L15 7" fill="none" stroke="white" stroke-width="2.4" '
           'stroke-linecap="round" stroke-linejoin="round"/></svg>')
    path = Path(tempfile.gettempdir()) / "splitternsp-check.svg"
    try:
        path.write_text(svg)
    except OSError:
        return QSS.replace('image: url("{CHECK}");', "")
    return QSS.replace("{CHECK}", path.as_posix())
