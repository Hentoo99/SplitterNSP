"""Custom UI components."""
from __future__ import annotations

import math
from typing import List, Optional

from PySide6.QtCore import (QEasingCurve, Property, QPointF, QPropertyAnimation, QRectF, QSize,
                            Qt, QTimer, Signal)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from ..inspector import KIND_BASE, KIND_DLC, KIND_UPDATE
from . import theme as T


def label(text: str = "", name: Optional[str] = None, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def chip(text: str, tone: str = "") -> QLabel:
    c = QLabel(text)
    c.setObjectName("chip")
    c.setProperty("tone", tone)
    c.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return c


def set_chip(c: QLabel, text: str, tone: str = "") -> None:
    c.setText(text)
    c.setProperty("tone", tone)
    c.style().unpolish(c)
    c.style().polish(c)


def notice(text: str, tone: str = "", icon: str = "ℹ︎") -> QFrame:
    f = QFrame()
    f.setObjectName("notice")
    f.setProperty("tone", tone)
    lay = QHBoxLayout(f)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(12)
    ic = label(icon)
    ic.setStyleSheet("font-size: 18px;")
    ic.setAlignment(Qt.AlignTop)
    txt = label(text, wrap=True)
    txt.setTextFormat(Qt.RichText)
    txt.setOpenExternalLinks(True)
    lay.addWidget(ic)
    lay.addWidget(txt, 1)
    f.text_label = txt
    f.icon_label = ic
    return f


def shadow(widget: QWidget, blur: int = 40, alpha: int = 120, dy: int = 10) -> None:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setColor(QColor(0, 0, 0, alpha))
    eff.setOffset(0, dy)
    widget.setGraphicsEffect(eff)


class GradientButton(QPushButton):
    """Primary button with a red→blue gradient."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)
        self.setMinimumWidth(150)
        self._hover = 0.0
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(160)

    def _get_hover(self):
        return self._hover

    def _set_hover(self, v):
        self._hover = v
        self.update()

    hover = Property(float, _get_hover, _set_hover)

    def enterEvent(self, e):
        self._anim.stop()
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._anim.stop()
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(e)

    def sizeHint(self):
        fm = self.fontMetrics()
        return QSize(max(150, fm.horizontalAdvance(self.text()) + 48), 42)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 11, 11)
        if self.isEnabled():
            g = QLinearGradient(r.topLeft(), r.topRight())
            c1, c2 = QColor(T.RED), QColor(T.BLUE)
            if self._hover:
                c1 = c1.lighter(100 + int(12 * self._hover))
                c2 = c2.lighter(100 + int(12 * self._hover))
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            if self.isDown():
                p.setOpacity(0.85)
            p.fillPath(path, g)
            p.setOpacity(1)
            gloss = QLinearGradient(r.topLeft(), r.bottomLeft())
            gloss.setColorAt(0, QColor(255, 255, 255, 40))
            gloss.setColorAt(0.5, QColor(255, 255, 255, 0))
            p.fillPath(path, gloss)
            p.setPen(QColor("white"))
        else:
            p.fillPath(path, QColor(T.SURFACE_3))
            p.setPen(QColor(T.DIM))
        f = self.font()
        f.setBold(True)
        f.setPixelSize(14)
        p.setFont(f)
        p.drawText(r, Qt.AlignCenter, self.text())


class Stepper(QWidget):
    """Vertical indicator of the wizard steps."""
    clicked = Signal(int)

    def __init__(self, steps: List[tuple], parent=None):
        super().__init__(parent)
        self.steps = steps  # [(title, description)]
        self.current = 0
        self.locked = False
        self.row_h = 74
        self.setMinimumHeight(self.row_h * len(steps))
        self.setCursor(Qt.PointingHandCursor)
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def _tick(self):
        self._pulse = (self._pulse + 0.04) % (2 * math.pi)
        self.update(0, self.current * self.row_h, 60, self.row_h)

    def set_current(self, i: int):
        self.current = i
        self.update()

    def mousePressEvent(self, e):
        i = int(e.position().y() // self.row_h)
        if not self.locked and 0 <= i < self.current:
            self.clicked.emit(i)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx = 30
        for i, (title, desc) in enumerate(self.steps):
            y = i * self.row_h
            cy = y + 24
            if i < len(self.steps) - 1:
                pen = QPen(QColor(T.BLUE if i < self.current else T.BORDER), 2)
                if i >= self.current:
                    pen.setStyle(Qt.DotLine)
                p.setPen(pen)
                p.drawLine(QPointF(cx, cy + 17), QPointF(cx, cy + self.row_h - 17))
            circle = QRectF(cx - 15, cy - 15, 30, 30)
            p.setPen(Qt.NoPen)
            if i == self.current:
                glow = QRadialGradient(QPointF(cx, cy), 26)
                a = int(70 + 50 * math.sin(self._pulse))
                glow.setColorAt(0, QColor(31, 182, 255, a))
                glow.setColorAt(1, QColor(31, 182, 255, 0))
                p.setBrush(glow)
                p.drawEllipse(QPointF(cx, cy), 26, 26)
                p.setBrush(T.accent_gradient(circle))
                p.drawEllipse(circle)
            elif i < self.current:
                p.setBrush(QColor(T.SURFACE_3))
                p.drawEllipse(circle)
            else:
                p.setBrush(QColor(T.SURFACE))
                p.setPen(QPen(QColor(T.BORDER), 1.5))
                p.drawEllipse(circle)
            f = QFont(self.font())
            f.setPixelSize(13)
            f.setBold(True)
            p.setFont(f)
            if i < self.current:
                p.setPen(QPen(QColor(T.GREEN), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                path = QPainterPath(QPointF(cx - 6, cy))
                path.lineTo(cx - 1.5, cy + 4.5)
                path.lineTo(cx + 6.5, cy - 4.5)
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
            else:
                p.setPen(QColor("white" if i == self.current else T.DIM))
                p.drawText(circle, Qt.AlignCenter, str(i + 1))
            f.setPixelSize(14)
            p.setFont(f)
            p.setPen(QColor(T.TEXT if i <= self.current else T.DIM))
            p.drawText(QRectF(cx + 28, cy - 18, 200, 20), Qt.AlignLeft | Qt.AlignVCenter, title)
            f.setBold(False)
            f.setPixelSize(12)
            p.setFont(f)
            p.setPen(QColor(T.MUTED if i <= self.current else T.DIM))
            p.drawText(QRectF(cx + 28, cy + 1, 200, 18), Qt.AlignLeft | Qt.AlignVCenter, desc)


class DropZone(QFrame):
    """Area to drop files onto, with an animated dashed border."""
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._active = False
        self._offset = 0.0
        self.compact = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _tick(self):
        self._offset = (self._offset + (1.2 if self._active else 0.25)) % 1000
        self.update()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._active = True

    def dragLeaveEvent(self, e):
        self._active = False

    def dropEvent(self, e):
        self._active = False
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(r, 18, 18)
        bg = QLinearGradient(r.topLeft(), r.bottomRight())
        a = 40 if self._active else 18
        bg.setColorAt(0, QColor(255, 61, 99, a))
        bg.setColorAt(1, QColor(31, 182, 255, a))
        p.fillPath(path, bg)
        pen = QPen(QBrush(T.accent_gradient(r)), 2 if self._active else 1.6)
        pen.setStyle(Qt.CustomDashLine)
        pen.setDashPattern([6, 5])
        pen.setDashOffset(-self._offset)
        p.setPen(pen)
        p.drawPath(path)
        if not self.compact:
            # icon: cartridge with an arrow
            cx, cy = r.center().x(), r.top() + 62
            card = QRectF(cx - 22, cy - 28, 44, 56)
            cp = QPainterPath()
            cp.moveTo(card.left() + 8, card.top())
            cp.lineTo(card.right() - 14, card.top())
            cp.lineTo(card.right(), card.top() + 14)
            cp.lineTo(card.right(), card.bottom() - 8)
            cp.quadTo(card.right(), card.bottom(), card.right() - 8, card.bottom())
            cp.lineTo(card.left() + 8, card.bottom())
            cp.quadTo(card.left(), card.bottom(), card.left(), card.bottom() - 8)
            cp.lineTo(card.left(), card.top() + 8)
            cp.quadTo(card.left(), card.top(), card.left() + 8, card.top())
            p.setPen(Qt.NoPen)
            p.fillPath(cp, T.accent_gradient(card))
            p.fillRect(QRectF(cx - 12, cy - 12, 24, 16), QColor(255, 255, 255, 60))
            bob = 3 * math.sin(self._offset / 6)
            p.setPen(QPen(QColor("white"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawLine(QPointF(cx, cy - 2 + bob), QPointF(cx, cy + 18 + bob))
            arrow = QPainterPath(QPointF(cx - 7, cy + 11 + bob))
            arrow.lineTo(cx, cy + 18 + bob)
            arrow.lineTo(cx + 7, cy + 11 + bob)
            p.setBrush(Qt.NoBrush)
            p.drawPath(arrow)


class GameCard(QFrame):
    """Game card with a faded banner, icon and details."""
    remove_requested = Signal(object)

    def __init__(self, item, removable: bool = True, height: int = 128, compact: bool = False,
                 parent=None):
        super().__init__(parent)
        self.item = item
        self.banner: Optional[QPixmap] = None
        self.setFixedHeight(height)
        pad = 12 if compact else 16
        self.icon_size = height - 2 * pad
        lay = QHBoxLayout(self)
        lay.setContentsMargins(pad, pad, 16, pad)
        lay.setSpacing(18)
        self.icon = QLabel()
        self.icon.setFixedSize(self.icon_size, self.icon_size)
        lay.addWidget(self.icon)
        col = QVBoxLayout()
        col.setSpacing(2 if compact else 4)
        col.addStretch()
        self.title = label("", "cardTitle")
        self.sub = label("", "cardSub")
        col.addWidget(self.title)
        col.addWidget(self.sub)
        col.addSpacing(2 if compact else 6)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(6)
        col.addLayout(self.chips)
        col.addStretch()
        lay.addLayout(col, 1)
        self.close_btn = None
        if removable:
            self.close_btn = QPushButton("✕")
            self.close_btn.setObjectName("close")
            self.close_btn.setFixedSize(28, 28)
            self.close_btn.setCursor(Qt.PointingHandCursor)
            self.close_btn.setToolTip("Remove from the list")
            self.close_btn.clicked.connect(lambda: self.remove_requested.emit(self.item))
            lay.addWidget(self.close_btn, 0, Qt.AlignTop)
        self.refresh()

    def refresh(self):
        it = self.item
        self.title.setText(self.title.fontMetrics().elidedText(it.name, Qt.ElideRight, 520))
        self.title.setToolTip(it.path.name)
        sub = [it.publisher] if it.publisher else []
        sub.append(it.info.title_id or "Title ID not found")
        self.sub.setText("  ·  ".join(sub))
        while self.chips.count():
            w = self.chips.takeAt(0).widget()
            if w:
                w.deleteLater()
        tone = {KIND_BASE: "blue", KIND_UPDATE: "purple", KIND_DLC: "amber"}.get(it.info.kind, "")
        self.chips.addWidget(chip(it.info.kind.upper(), tone))
        if it.info.version and it.info.version != "0":
            self.chips.addWidget(chip(f"v{it.info.version}"))
        self.chips.addWidget(chip(it.size_label))
        if it.split:
            self.chips.addWidget(chip(f"✂  {it.parts} PARTS", "red"))
        else:
            self.chips.addWidget(chip("✓  NO SPLIT NEEDED", "green"))
        self.chips.addStretch()
        pix = it.icon or T.placeholder_icon(it.name, 256)
        self.icon.setPixmap(T.rounded(pix, self.icon_size, 0.18))
        self.banner = it.banner
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 16, 16)
        p.fillPath(path, QColor(T.SURFACE))
        p.setClipPath(path)
        if self.banner and not self.banner.isNull():
            # banner on the right, cropped to fill
            bw = r.width() * 0.62
            target = QRectF(r.right() - bw, r.top(), bw, r.height())
            src = QRectF(self.banner.rect())
            scale = max(target.width() / src.width(), target.height() / src.height())
            sw, sh = target.width() / scale, target.height() / scale
            src = QRectF(src.center().x() - sw / 2, src.center().y() - sh / 2 - sh * 0.05, sw, sh)
            p.setOpacity(0.55)
            p.drawPixmap(target, self.banner, src)
            p.setOpacity(1)
            fade = QLinearGradient(target.topLeft(), target.topRight())
            fade.setColorAt(0, QColor(T.SURFACE))
            fade.setColorAt(0.55, QColor(22, 26, 35, 150))
            fade.setColorAt(1, QColor(22, 26, 35, 40))
            p.fillRect(target, fade)
        else:
            c1, c2 = T.color_pair(self.item.name)
            g = QRadialGradient(QPointF(r.right() - 60, r.top()), r.width() * 0.5)
            c1.setAlpha(55)
            c2.setAlpha(0)
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            p.fillRect(r, g)
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.drawPath(path)


class ProgressRing(QWidget):
    """Progress ring with a conical gradient."""

    def __init__(self, size: int = 190, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._value = 0.0
        self._shown = 0.0
        self.caption = ""
        self._spin = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_value(self, v: float):
        self._value = max(0.0, min(1.0, v))

    def _tick(self):
        self._shown += (self._value - self._shown) * 0.12
        self._spin = (self._spin + 2.0) % 360
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        w = 14
        r = QRectF(w, w, s - 2 * w, s - 2 * w)
        p.setPen(QPen(QColor(T.SURFACE_3), w, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 0, 360 * 16)
        if self._shown > 0.002:
            g = QConicalGradient(r.center(), 90)
            g.setColorAt(0, QColor(T.RED))
            g.setColorAt(0.5, QColor(T.PURPLE))
            g.setColorAt(1, QColor(T.BLUE))
            p.setPen(QPen(QBrush(g), w, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(r, 90 * 16, -int(360 * 16 * self._shown))
            # glowing dot at the head of the arc
            ang = math.radians(90 - 360 * self._shown)
            hx = r.center().x() + math.cos(ang) * r.width() / 2
            hy = r.center().y() - math.sin(ang) * r.height() / 2
            glow = QRadialGradient(QPointF(hx, hy), w * 1.4)
            glow.setColorAt(0, QColor(255, 255, 255, 160))
            glow.setColorAt(1, QColor(255, 255, 255, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QPointF(hx, hy), w * 1.4, w * 1.4)
        f = QFont(self.font())
        f.setPixelSize(int(s * 0.2))
        f.setWeight(QFont.Black)
        p.setFont(f)
        p.setPen(QColor(T.TEXT))
        p.drawText(QRectF(0, 0, s, s * 0.95), Qt.AlignCenter, f"{int(self._shown * 100 + 0.5)}%")
        f.setPixelSize(12)
        f.setWeight(QFont.Medium)
        p.setFont(f)
        p.setPen(QColor(T.MUTED))
        p.drawText(QRectF(0, s * 0.58, s, 20), Qt.AlignCenter, self.caption)


class SelectCard(QFrame):
    """Selectable card (for choosing the destination)."""
    selected = Signal(object)

    def __init__(self, payload, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.is_selected = False
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False

    def set_selected(self, v: bool):
        self.is_selected = v
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        self.selected.emit(self.payload)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 16, 16)
        p.fillPath(path, QColor(T.SURFACE_2 if (self._hover or self.is_selected) else T.SURFACE))
        if self.is_selected:
            bg = QLinearGradient(r.topLeft(), r.bottomRight())
            bg.setColorAt(0, QColor(255, 61, 99, 26))
            bg.setColorAt(1, QColor(31, 182, 255, 26))
            p.fillPath(path, bg)
            p.setPen(QPen(QBrush(T.accent_gradient(r)), 2))
        else:
            p.setPen(QPen(QColor(T.BORDER), 1))
        p.drawPath(path)


class DriveIcon(QWidget):
    """Hand-drawn icon of an SD card (or a folder)."""

    def __init__(self, kind: str = "sd", colors=(T.RED, T.BLUE), parent=None):
        super().__init__(parent)
        self.kind = kind
        self.colors = colors
        self.setFixedSize(54, 64)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(5, 4, 44, 56)
        g = T.accent_gradient(r, *self.colors)
        if self.kind == "folder":
            path = QPainterPath()
            path.addRoundedRect(QRectF(2, 14, 50, 38), 7, 7)
            tab = QPainterPath()
            tab.addRoundedRect(QRectF(2, 8, 22, 14), 5, 5)
            p.fillPath(tab.united(path), g)
            p.fillRect(QRectF(2, 22, 50, 2), QColor(255, 255, 255, 60))
            return
        path = QPainterPath()
        path.moveTo(r.left() + 6, r.top())
        path.lineTo(r.right() - 14, r.top())
        path.lineTo(r.right(), r.top() + 14)
        path.lineTo(r.right(), r.bottom() - 6)
        path.quadTo(r.right(), r.bottom(), r.right() - 6, r.bottom())
        path.lineTo(r.left() + 6, r.bottom())
        path.quadTo(r.left(), r.bottom(), r.left(), r.bottom() - 6)
        path.lineTo(r.left(), r.top() + 6)
        path.quadTo(r.left(), r.top(), r.left() + 6, r.top())
        p.fillPath(path, g)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 110))
        for i in range(4):
            p.drawRoundedRect(QRectF(r.left() + 7 + i * 7.5, r.top() + 5, 4.5, 11), 1.5, 1.5)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawRoundedRect(QRectF(r.left() + 7, r.top() + 26, 30, 22), 4, 4)


class SpaceBar(QWidget):
    """Space bar: used / about to be used / free."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.total = 1
        self.used = 0
        self.incoming = 0

    def set_values(self, total: int, free: int, incoming: int = 0):
        self.total = max(total, 1)
        self.used = total - free
        self.incoming = incoming
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        bg = QPainterPath()
        bg.addRoundedRect(r, 4, 4)
        p.fillPath(bg, QColor(T.SURFACE_3))
        p.setClipPath(bg)
        uw = r.width() * self.used / self.total
        p.fillRect(QRectF(0, 0, uw, r.height()), QColor("#55607a"))
        if self.incoming:
            iw = r.width() * self.incoming / self.total
            over = self.used + self.incoming > self.total
            g = T.accent_gradient(QRectF(uw, 0, iw, r.height()),
                                  T.RED if over else T.RED, T.RED if over else T.BLUE)
            p.fillRect(QRectF(uw, 0, iw, r.height()), g)


class StatTile(QFrame):
    def __init__(self, value: str, caption: str, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(2)
        self.value = label(value, "statValue")
        self.caption = label(caption, "statLabel")
        lay.addWidget(self.value)
        lay.addWidget(self.caption)


class SuccessBadge(QWidget):
    """Big animated checkmark for the final screen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self._t = 0.0
        self.ok = True
        self._anim = QPropertyAnimation(self, b"t", self)
        self._anim.setDuration(900)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _get_t(self):
        return self._t

    def _set_t(self, v):
        self._t = v
        self.update()

    t = Property(float, _get_t, _set_t)

    def play(self, ok: bool = True):
        self.ok = ok
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(60, 60)
        t = self._t
        glow = QRadialGradient(c, 60)
        col = QColor(T.GREEN if self.ok else T.AMBER)
        col.setAlpha(int(90 * t))
        glow.setColorAt(0, col)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, 60, 60)
        rr = 40 * min(1.0, t * 1.6)
        circle = QRectF(c.x() - rr, c.y() - rr, 2 * rr, 2 * rr)
        if self.ok:
            p.setBrush(T.accent_gradient(circle, T.GREEN, T.BLUE))
        else:
            p.setBrush(T.accent_gradient(circle, T.AMBER, T.RED))
        p.drawEllipse(circle)
        k = max(0.0, min(1.0, (t - 0.35) / 0.65))
        if k <= 0:
            return
        p.setPen(QPen(QColor("white"), 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if self.ok:
            pts = [QPointF(42, 61), QPointF(54, 73), QPointF(78, 49)]
            path = QPainterPath(pts[0])
            seg1 = min(1.0, k * 2.5)
            path.lineTo(pts[0] + (pts[1] - pts[0]) * seg1)
            if k > 0.4:
                seg2 = (k - 0.4) / 0.6
                path.lineTo(pts[1] + (pts[2] - pts[1]) * seg2)
            p.drawPath(path)
        else:
            p.drawLine(QPointF(60, 42), QPointF(60, 42 + 22 * k))
            if k > 0.8:
                p.drawPoint(QPointF(60, 78))
