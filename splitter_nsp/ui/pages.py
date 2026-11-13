"""The five screens of the wizard."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QProgressBar, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from .. import volumes
from ..inspector import SUPPORTED_EXTENSIONS
from ..volumes import Volume, human
from . import theme as T
from .models import Destination, GameItem
from .widgets import (DriveIcon, DropZone, GameCard, ProgressRing, SelectCard, SpaceBar,
                      StatTile, SuccessBadge, chip, label, notice, set_chip)


def header(title: str, subtitle: str) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(6)
    lay.addWidget(label(title, "h1"))
    lay.addWidget(label(subtitle, "sub", wrap=True))
    return lay


def scroll_column() -> tuple:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    inner = QWidget()
    col = QVBoxLayout(inner)
    col.setContentsMargins(0, 0, 8, 0)
    col.setSpacing(12)
    col.addStretch()
    area.setWidget(inner)
    return area, col


class Page(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(40, 34, 40, 20)
        self.root.setSpacing(20)

    def can_continue(self) -> bool:
        return True


# --------------------------------------------------------------------------- #
#  1. Game selection
# --------------------------------------------------------------------------- #

class GamesPage(Page):
    add_paths = Signal(list)
    remove_item = Signal(object)

    def __init__(self):
        super().__init__()
        self.root.addLayout(header(
            "Pick your games",
            "Drag in your NSP, NSZ or XCI files. Anything over 4 GB gets split into parts "
            "that work on FAT32 SD cards; everything else is copied as is."))

        self.drop = DropZone()
        self.drop.files_dropped.connect(self.add_paths.emit)
        dl = QVBoxLayout(self.drop)
        dl.setContentsMargins(24, 24, 24, 24)

        # large content (empty list)
        self.big = QWidget()
        bl = QVBoxLayout(self.big)
        bl.setContentsMargins(0, 104, 0, 10)
        bl.setSpacing(6)
        t = label("Drop your games here", "h2")
        t.setAlignment(Qt.AlignCenter)
        s = label("or pick files from your computer", "muted")
        s.setAlignment(Qt.AlignCenter)
        bl.addWidget(t)
        bl.addWidget(s)
        bl.addSpacing(12)
        row = QHBoxLayout()
        row.addStretch()
        self.btn_files = QPushButton("📂  Browse files…")
        self.btn_folder = QPushButton("🗂  Add folder…")
        for b in (self.btn_files, self.btn_folder):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        row.addStretch()
        bl.addLayout(row)
        bl.addStretch()

        # compact content (list has items)
        self.small = QWidget()
        sl = QHBoxLayout(self.small)
        sl.setContentsMargins(6, 0, 0, 0)
        sl.addWidget(label("＋  Drop more games here", "h2"))
        sl.addStretch()
        self.btn_files2 = QPushButton("Browse files…")
        self.btn_folder2 = QPushButton("Add folder…")
        for b in (self.btn_files2, self.btn_folder2):
            b.setCursor(Qt.PointingHandCursor)
            sl.addWidget(b)

        dl.addWidget(self.big)
        dl.addWidget(self.small)
        self.root.addWidget(self.drop)

        self.area, self.col = scroll_column()
        self.root.addWidget(self.area, 1)
        self.summary = label("", "muted")
        self.root.addWidget(self.summary)

        for b in (self.btn_files, self.btn_files2):
            b.clicked.connect(self._pick_files)
        for b in (self.btn_folder, self.btn_folder2):
            b.clicked.connect(self._pick_folder)
        self.cards: Dict[int, GameCard] = {}
        self.items: List[GameItem] = []
        self.set_items([])

    def _pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Pick your games", str(Path.home()),
            "Switch games (*.nsp *.nsz *.xci *.xcz);;All files (*)")
        if files:
            self.add_paths.emit(files)

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Pick a folder with your games",
                                             str(Path.home()))
        if d:
            self.add_paths.emit([d])

    def set_items(self, items: List[GameItem]):
        self.items = items
        alive = {id(i) for i in items}
        for key in list(self.cards):
            if key not in alive:
                self.cards.pop(key).deleteLater()
        for idx, it in enumerate(items):
            card = self.cards.get(id(it))
            if card is None:
                card = GameCard(it)
                card.remove_requested.connect(self.remove_item.emit)
                self.cards[id(it)] = card
            self.col.insertWidget(idx, card)
        empty = not items
        self.big.setVisible(empty)
        self.small.setVisible(not empty)
        self.drop.compact = not empty
        self.drop.setFixedHeight(300 if empty else 84)
        if empty:
            self.summary.setText("")
        else:
            total = sum(i.size for i in items)
            n_split = sum(1 for i in items if i.split)
            self.summary.setText(
                f"<b>{len(items)}</b> {'file' if len(items) == 1 else 'files'}  ·  "
                f"<b>{human(total)}</b>  ·  "
                f"<span style='color:#ff7d97'><b>{n_split}</b> to split</span>  ·  "
                f"<span style='color:#5fe3a8'><b>{len(items) - n_split}</b> to copy</span>")
        self.changed.emit()

    def refresh_item(self, item: GameItem):
        card = self.cards.get(id(item))
        if card:
            card.refresh()

    def can_continue(self) -> bool:
        return bool(self.items)


# --------------------------------------------------------------------------- #
#  2. Destination
# --------------------------------------------------------------------------- #

class DestinationPage(Page):
    def __init__(self):
        super().__init__()
        top = QHBoxLayout()
        top.addLayout(header(
            "Where should they go?",
            "Put your console's SD card in the computer and select it. "
            "You can also save to any folder and copy the files over later."), 1)
        self.btn_refresh = QPushButton("⟳  Refresh")
        self.btn_refresh.setObjectName("ghost")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh)
        top.addWidget(self.btn_refresh, 0, Qt.AlignTop)
        self.root.addLayout(top)

        self.area, self.col = scroll_column()
        self.root.addWidget(self.area, 1)

        sub = QHBoxLayout()
        sub.setSpacing(12)
        sub.addWidget(label("Folder on the destination:", "muted"))
        self.subfolder = QLineEdit()
        self.subfolder.setPlaceholderText("(root)  e.g. NSP")
        self.subfolder.setText("NSP")
        self.subfolder.setMaximumWidth(260)
        self.subfolder.textChanged.connect(lambda _: self.changed.emit())
        sub.addWidget(self.subfolder)
        sub.addStretch()
        self.root.addLayout(sub)

        self.info = notice("")
        self.root.addWidget(self.info)

        self.cards: List[SelectCard] = []
        self.selected: Optional[Destination] = None
        self.custom: Optional[Destination] = None
        self.needed = 0
        self._signature = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._auto_refresh)

    def showEvent(self, e):
        self.refresh()
        self.timer.start(2500)
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def _auto_refresh(self):
        sig = tuple(v.mount_point for v in volumes.external_volumes())
        if sig != self._signature:
            self.refresh()

    def refresh(self):
        vols = volumes.external_volumes()
        self._signature = tuple(v.mount_point for v in vols)
        for c in self.cards:
            c.deleteLater()
        self.cards = []
        dests = [Destination(Path(v.mount_point), v) for v in vols]
        if self.custom:
            dests.append(self.custom)
        for d in dests:
            card = self._make_card(d)
            self.col.insertWidget(self.col.count() - 1, card)
            self.cards.append(card)
        other = self._make_other_card()
        self.col.insertWidget(self.col.count() - 1, other)
        self.cards.append(other)

        if not vols:
            empty = notice("No SD card found. Insert one into the reader and it will show "
                           "up here automatically.", "amber", "💾")
            self.col.insertWidget(0, empty)
            self.cards.append(empty)

        # keep the selection if it's still there
        keep = None
        if self.selected:
            for d in dests:
                if d.folder == self.selected.folder:
                    keep = d
        if keep is None and dests and dests[0].is_fat and not self.selected:
            keep = dests[0]
        self._select(keep)

    def _make_card(self, d: Destination) -> SelectCard:
        v = d.volume
        card = SelectCard(d)
        card.setFixedHeight(96)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(18, 14, 22, 14)
        lay.setSpacing(16)
        lay.addWidget(DriveIcon("folder" if d.custom else "sd",
                                (T.RED, T.BLUE) if (v and v.is_fat) else (T.PURPLE, T.BLUE)))
        col = QVBoxLayout()
        col.setSpacing(5)
        row = QHBoxLayout()
        row.setSpacing(8)
        name = d.folder.name if d.custom else (v.name if v else str(d.folder))
        row.addWidget(label(name, "cardTitle"))
        if v:
            tone = "green" if v.is_fat else ("blue" if v.fs_type == "exfat" else "")
            row.addWidget(chip(v.format_label, tone))
        row.addStretch()
        col.addLayout(row)
        bar = SpaceBar()
        if v:
            bar.set_values(v.total, v.free, self.needed)
        col.addWidget(bar)
        free = f"{human(v.free)} free of {human(v.total)}" if v else ""
        col.addWidget(label(f"{free}   ·   {d.folder}", "dim"))
        lay.addLayout(col, 1)
        card.selected.connect(self._select)
        return card

    def _make_other_card(self) -> SelectCard:
        card = SelectCard("other")
        card.setFixedHeight(72)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(18, 10, 22, 10)
        lay.setSpacing(16)
        ic = DriveIcon("folder", (T.SURFACE_3, "#3a4357"))
        ic.setFixedSize(54, 52)
        lay.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label("Choose another folder…", "cardTitle"))
        col.addWidget(label("Save the parts on your computer and copy them to the SD card later",
                            "dim"))
        lay.addLayout(col, 1)
        card.selected.connect(lambda _: self._choose_other())
        return card

    def _choose_other(self):
        d = QFileDialog.getExistingDirectory(self, "Choose the destination folder",
                                             str(Path.home()))
        if not d:
            return
        path = Path(d)
        vol = volumes.volume_for_path(path)
        if vol and Path(vol.mount_point) == path:
            dest = Destination(path, vol)
        else:
            dest = Destination(path, vol, custom=True)
            self.custom = dest
        self.selected = dest
        self.refresh()

    def _select(self, d):
        if d == "other":
            return
        self.selected = d
        for c in self.cards:
            if isinstance(c, SelectCard) and c.payload != "other":
                c.set_selected(d is not None and c.payload.folder == d.folder)
        self._update_info()
        self.changed.emit()

    def _update_info(self):
        d = self.selected
        if d is None:
            self.info.hide()
            return
        self.info.show()
        v = d.volume
        if v and v.is_fat:
            msg, tone, ic = ("Perfect: the card is <b>FAT32</b>. Files over 4 GB will be split "
                             "and their folders will get the archive bit, so the console sees "
                             "each one as a single file.", "green", "✅")
        elif v and v.fs_type == "exfat":
            msg, tone, ic = ("The destination is <b>exFAT</b>, which handles files over 4 GB: "
                             "splitting isn't strictly needed, but I'll do it anyway in case you "
                             "want to copy the parts to a FAT32 SD card later.", "", "ℹ︎")
        else:
            msg, tone, ic = ("The parts will be saved in this folder. When you copy them to a "
                             "FAT32 SD card, remember to set the archive bit (in Hekate: "
                             "<i>Tools → Arch bit • RCM • Touch → Fix Archive bit</i>).",
                             "amber", "💡")
        self.info.text_label.setText(msg)
        self.info.icon_label.setText(ic)
        self.info.setProperty("tone", tone)
        self.info.style().unpolish(self.info)
        self.info.style().polish(self.info)

    def destination(self) -> Optional[Destination]:
        if self.selected is None:
            return None
        d = self.selected
        return Destination(d.folder, d.volume, self.subfolder.text(), d.custom)

    def can_continue(self) -> bool:
        return self.selected is not None


# --------------------------------------------------------------------------- #
#  3. Review
# --------------------------------------------------------------------------- #

class ReviewPage(Page):
    def __init__(self):
        super().__init__()
        self.root.addLayout(header("Review",
                                   "Make sure everything looks right, then hit Start."))
        self.tiles = QHBoxLayout()
        self.tiles.setSpacing(12)
        self.t_games = StatTile("0", "files selected")
        self.t_split = StatTile("0", "to split")
        self.t_need = StatTile("0", "space needed")
        self.t_free = StatTile("0", "free afterwards")
        for t in (self.t_games, self.t_split, self.t_need, self.t_free):
            self.tiles.addWidget(t)
        self.root.addLayout(self.tiles)

        self.dest_label = label("", "muted")
        self.dest_label.setTextFormat(Qt.RichText)
        self.root.addWidget(self.dest_label)

        self.area, self.col = scroll_column()
        self.col.setSpacing(8)
        self.root.addWidget(self.area, 1)

        opts = QFrame()
        opts.setObjectName("panel")
        ol = QVBoxLayout(opts)
        ol.setContentsMargins(18, 14, 18, 14)
        ol.setSpacing(8)
        self.cb_archive = QCheckBox(
            "Set the archive bit on the folders automatically (recommended)")
        self.cb_archive.setChecked(True)
        self.archive_hint = label("", "dim", wrap=True)
        self.cb_eject = QCheckBox("Eject the card when finished")
        ol.addWidget(self.cb_archive)
        ol.addWidget(self.archive_hint)
        ol.addWidget(self.cb_eject)
        self.root.addWidget(opts)
        self.warn = notice("", "red", "⚠️")
        self.root.addWidget(self.warn)
        self.ok_space = True
        self.cards: List[QWidget] = []

    def populate(self, items: List[GameItem], dest: Destination):
        for c in self.cards:
            c.deleteLater()
        self.cards = []
        root = dest.root
        need = sum(i.size for i in items)
        free = dest.volume.free if dest.volume else 0
        # files that will be overwritten free up space
        existing = 0
        overwrite = []
        for it in items:
            t = root / it.target_name
            if t.exists():
                overwrite.append(it.name)
                if t.is_dir():
                    existing += sum(p.stat().st_size for p in t.iterdir() if p.is_file())
                else:
                    existing += t.stat().st_size
        free_after = free + existing - need
        self.ok_space = free_after > 0 or not dest.volume

        self.t_games.value.setText(str(len(items)))
        self.t_split.value.setText(str(sum(1 for i in items if i.split)))
        self.t_need.value.setText(human(need))
        self.t_free.value.setText(human(max(free_after, 0)) if dest.volume else "—")
        self.t_free.value.setStyleSheet(f"color: {T.RED};" if not self.ok_space else "")

        vol = dest.volume
        self.dest_label.setText(
            f"Destination:&nbsp; <b style='color:{T.TEXT}'>{root}</b>"
            + (f"&nbsp;&nbsp;<span style='color:{T.MUTED}'>({vol.format_label})</span>" if vol else ""))

        for idx, it in enumerate(items):
            card = GameCard(it, removable=False, height=100, compact=True)
            target = (f"→  folder <b>{it.target_name}</b> with {it.parts} parts "
                      f"(00…{it.parts - 1:02d})" if it.split
                      else f"→  copied as <b>{it.target_name}</b>")
            card.sub.setText(target)
            card.sub.setTextFormat(Qt.RichText)
            self.col.insertWidget(idx, card)
            self.cards.append(card)

        has_split = any(i.split for i in items)
        can_fix = has_split and dest.is_fat
        self.cb_archive.setVisible(has_split)
        self.cb_archive.setEnabled(can_fix)
        self.cb_archive.setChecked(can_fix)
        if not has_split:
            self.archive_hint.setText("Nothing to split, so the archive bit isn't needed.")
        elif not dest.is_fat:
            self.archive_hint.setText("Only available when writing straight to a FAT32 SD "
                                      "card. After copying, use Hekate → Tools → "
                                      "Fix Archive bit.")
        elif sys.platform == "darwin":
            self.archive_hint.setText("macOS doesn't normally allow this: the card will be "
                                      "unmounted for a moment and you'll be asked for your "
                                      "administrator password.")
        else:
            self.archive_hint.setText("It will be set using the system tools.")
        self.cb_eject.setVisible(bool(vol) and not dest.custom and sys.platform == "darwin")
        self.cb_eject.setChecked(False)

        warns = []
        if not self.ok_space:
            warns.append(f"Not enough space: you're <b>{human(-free_after)}</b> short. "
                         "Remove some games or free up space on the card.")
        if overwrite:
            warns.append("Already there, will be replaced: " + ", ".join(overwrite[:4])
                         + ("…" if len(overwrite) > 4 else ""))
        self.warn.setVisible(bool(warns))
        self.warn.text_label.setText("<br>".join(warns))
        tone = "red" if not self.ok_space else "amber"
        self.warn.setProperty("tone", tone)
        self.warn.style().unpolish(self.warn)
        self.warn.style().polish(self.warn)

    def can_continue(self) -> bool:
        return self.ok_space


# --------------------------------------------------------------------------- #
#  4. Processing
# --------------------------------------------------------------------------- #

class QueueRow(QFrame):
    def __init__(self, item: GameItem):
        super().__init__()
        self.setObjectName("panel")
        self.setFixedHeight(56)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 14, 8)
        lay.setSpacing(12)
        ic = QLabel()
        ic.setPixmap(T.rounded(item.icon or T.placeholder_icon(item.name, 128), 40, 0.22))
        lay.addWidget(ic)
        name = label(item.name)
        name.setStyleSheet("font-weight: 600;")
        lay.addWidget(name, 1)
        self.status = chip("QUEUED")
        lay.addWidget(self.status)

    def set_status(self, text: str, tone: str):
        set_chip(self.status, text, tone)


class ProgressPage(Page):
    def __init__(self):
        super().__init__()
        self.title = label("Working on it…", "h1", wrap=True)
        self.subtitle = label("Don't remove the card until I'm done.", "sub")
        self.root.addWidget(self.title)
        self.root.addWidget(self.subtitle)

        hero = QHBoxLayout()
        hero.setSpacing(26)
        self.ring = ProgressRing(200)
        hero.addWidget(self.ring, 0, Qt.AlignVCenter)
        right = QVBoxLayout()
        right.setSpacing(10)
        self.card_holder = QVBoxLayout()
        right.addLayout(self.card_holder)
        self.item_bar = QProgressBar()
        self.item_bar.setRange(0, 1000)
        self.item_bar.setFixedHeight(10)
        right.addWidget(self.item_bar)
        stats = QHBoxLayout()
        self.lb_part = label("", "muted")
        self.lb_speed = label("", "muted")
        self.lb_eta = label("", "muted")
        stats.addWidget(self.lb_part)
        stats.addStretch()
        stats.addWidget(self.lb_speed)
        stats.addSpacing(20)
        stats.addWidget(self.lb_eta)
        right.addLayout(stats)
        hero.addLayout(right, 1)
        self.root.addLayout(hero)

        self.root.addWidget(label("QUEUE", "dim"))
        self.area, self.col = scroll_column()
        self.col.setSpacing(8)
        self.root.addWidget(self.area, 1)
        self.rows: List[QueueRow] = []
        self.card: Optional[GameCard] = None

    def start(self, items: List[GameItem]):
        self.items = items
        self.total = sum(i.size for i in items) or 1
        for r in self.rows:
            r.deleteLater()
        self.rows = []
        for idx, it in enumerate(items):
            row = QueueRow(it)
            self.col.insertWidget(idx, row)
            self.rows.append(row)
        self.ring.set_value(0)
        self.ring.caption = "complete"
        self.title.setText("Working on it…")
        self.subtitle.setText("Don't remove the card until I'm done.")
        self.item_bar.setValue(0)
        self.samples = []
        self.lb_part.setText("")
        self.lb_speed.setText("")
        self.lb_eta.setText("")

    def on_item_started(self, i: int):
        it = self.items[i]
        if self.card:
            self.card.deleteLater()
        self.card = GameCard(it, removable=False, height=120)
        self.card_holder.addWidget(self.card)
        self.rows[i].set_status("WORKING", "blue")
        self.area.ensureWidgetVisible(self.rows[i])
        self.title.setText(("Splitting " if it.split else "Copying ") + it.name)

    def on_progress(self, total_done, i: int, item_done):
        it = self.items[i]
        self.ring.set_value(total_done / self.total)
        self.item_bar.setValue(int(1000 * item_done / max(it.size, 1)))
        if it.split:
            from .. import engine
            part = min(item_done // engine.PART_SIZE + 1, it.parts)
            self.lb_part.setText(f"Part {part} of {it.parts}  ·  "
                                 f"{human(item_done)} of {it.size_label}")
        else:
            self.lb_part.setText(f"{human(item_done)} of {it.size_label}")
        now = time.monotonic()
        self.samples.append((now, total_done))
        self.samples = [s for s in self.samples if now - s[0] < 4]
        if len(self.samples) > 1 and now - self.samples[0][0] > 0.5:
            dt = now - self.samples[0][0]
            speed = (total_done - self.samples[0][1]) / dt
            self.lb_speed.setText(f"⚡ {human(speed)}/s")
            if speed > 0:
                left = (self.total - total_done) / speed
                m, s = divmod(int(left), 60)
                h, m = divmod(m, 60)
                eta = f"{h} h {m} min" if h else (f"{m} min {s:02d} s" if m else f"{s} s")
                self.lb_eta.setText(f"⏱ {eta} left")

    def on_item_finished(self, i: int, ok: bool, err: str):
        if ok:
            self.rows[i].set_status("✓ DONE", "green")
        else:
            self.rows[i].set_status("ERROR" if err != "Cancelled" else "CANCELLED", "red")
            self.rows[i].setToolTip(err)

    def on_phase(self, text: str):
        self.title.setText(text)
        self.subtitle.setText("Almost done…")
        self.lb_speed.setText("")
        self.lb_eta.setText("")


# --------------------------------------------------------------------------- #
#  5. Done
# --------------------------------------------------------------------------- #

class DonePage(Page):
    restart = Signal()

    def __init__(self):
        super().__init__()
        self.root.setSpacing(14)
        top = QHBoxLayout()
        top.setSpacing(20)
        self.badge = SuccessBadge()
        top.addWidget(self.badge)
        tl = QVBoxLayout()
        tl.addStretch()
        self.title = label("All set!", "h1")
        self.subtitle = label("", "sub", wrap=True)
        tl.addWidget(self.title)
        tl.addWidget(self.subtitle)
        tl.addStretch()
        top.addLayout(tl, 1)
        self.root.addLayout(top)

        self.arch = notice("", "green", "✅")
        self.root.addWidget(self.arch)

        steps = QFrame()
        steps.setObjectName("panel")
        sl = QVBoxLayout(steps)
        sl.setContentsMargins(22, 18, 22, 18)
        sl.setSpacing(10)
        sl.addWidget(label("What's next?", "h2"))
        self.steps_label = label("", wrap=True)
        self.steps_label.setTextFormat(Qt.RichText)
        sl.addWidget(self.steps_label)
        self.root.addWidget(steps)

        self.errors = notice("", "red", "⚠️")
        self.root.addWidget(self.errors)
        self.root.addStretch()

        row = QHBoxLayout()
        self.btn_show = QPushButton("📂  Show files")
        self.btn_eject = QPushButton("⏏  Eject card")
        self.btn_restart = QPushButton("↺  Split more games")
        for b in (self.btn_show, self.btn_eject, self.btn_restart):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        row.addStretch()
        self.root.addLayout(row)
        self.btn_show.clicked.connect(self._show)
        self.btn_eject.clicked.connect(self._eject)
        self.btn_restart.clicked.connect(self.restart.emit)
        self.dest: Optional[Destination] = None

    def show_result(self, items: List[GameItem], dest: Destination, cancelled: bool,
                    arch_requested: bool, arch_ok: bool, arch_msg: str, ejected: bool):
        self.dest = dest
        ok_items = [i for i in items if i.status == "done"]
        bad = [i for i in items if i.status == "error"]
        n_split = sum(1 for i in ok_items if i.split)
        success = not cancelled and not bad
        self.badge.play(success)
        if cancelled:
            self.title.setText("Operation cancelled")
        elif bad:
            self.title.setText("Finished with some errors")
        else:
            self.title.setText("All set!")
        self.subtitle.setText(
            f"{len(ok_items)} of {len(items)} files ready in {dest.root}"
            + (f"  ·  {n_split} split into parts" if n_split else ""))

        has_split = n_split > 0
        hekate = ("If a game doesn't show up, launch <b>Hekate</b> → <i>Tools</i> → "
                  "<i>Arch bit • RCM • Touch</i> → <b>Fix Archive bit</b>.")
        if not has_split:
            self.arch.hide()
        else:
            self.arch.show()
            if arch_requested and arch_ok:
                txt, tone, ic = ("Archive bit set: the console will see each <b>.nsp</b> "
                                 "folder as a single file.", "green", "✅")
            elif arch_requested:
                txt, tone, ic = (f"I couldn't set the archive bit: "
                                 f"{arch_msg}<br>{hekate}", "amber", "⚠️")
            else:
                txt, tone, ic = ("Remember to set the archive bit after copying the "
                                 f"folders to the FAT32 SD card. {hekate}", "amber", "💡")
            self.arch.text_label.setText(txt)
            self.arch.icon_label.setText(ic)
            self.arch.setProperty("tone", tone)
            self.arch.style().unpolish(self.arch)
            self.arch.style().polish(self.arch)

        first = ("Safely eject the card and put it in the console."
                 if dest.volume and not dest.custom else
                 "Copy the folder's contents to the console's (FAT32) SD card.")
        self.steps_label.setText(
            f"<p style='line-height:150%'>"
            f"<b style='color:{T.BLUE}'>1.</b>&nbsp; {first}<br>"
            f"<b style='color:{T.BLUE}'>2.</b>&nbsp; Launch your installer (DBI, Tinfoil, Awoo…) "
            f"and open the <b>{dest.subfolder.strip() or '/'}</b> folder on the card.<br>"
            f"<b style='color:{T.BLUE}'>3.</b>&nbsp; The <b>.nsp</b> folders show up as regular "
            f"files: install them as usual.</p>")

        self.errors.setVisible(bool(bad))
        self.errors.text_label.setText("<br>".join(f"<b>{i.name}</b>: {i.error}" for i in bad))
        can_eject = bool(dest.volume) and not dest.custom and sys.platform == "darwin" and not ejected
        self.btn_eject.setVisible(can_eject)
        self.btn_eject.setEnabled(True)
        self.btn_eject.setText("⏏  Eject card")
        self.btn_show.setVisible(not ejected)

    def _show(self):
        if not self.dest:
            return
        path = str(self.dest.root)
        if sys.platform == "darwin":
            subprocess.run(["open", path])
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", path])

    def _eject(self):
        if not (self.dest and self.dest.volume):
            return
        r = subprocess.run(["diskutil", "eject", self.dest.volume.mount_point],
                           capture_output=True, text=True)
        self.btn_eject.setText("✓  Card ejected" if r.returncode == 0 else "Eject failed")
        self.btn_eject.setEnabled(False)
        if r.returncode == 0:
            self.btn_show.hide()
