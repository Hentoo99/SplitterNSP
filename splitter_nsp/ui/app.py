"""Main window and wizard logic."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QThreadPool
from PySide6.QtGui import QColor, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QMainWindow, QMessageBox, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..inspector import KIND_DLC, KIND_UPDATE, SUPPORTED_EXTENSIONS
from . import theme as T
from .models import Destination, GameItem, MetaBus, MetaTask, SplitWorker
from .pages import DestinationPage, DonePage, GamesPage, ProgressPage, ReviewPage
from .widgets import GradientButton, Stepper, label

STEPS = [
    ("Games", "Pick what to split"),
    ("Destination", "SD card or folder"),
    ("Review", "Check and start"),
    ("Processing", "Splitting and copying"),
    ("Done", "Ready for the console"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 780)
        self.setMinimumSize(1000, 680)
        self.items: List[GameItem] = []
        self.worker: Optional[SplitWorker] = None
        self.dest: Optional[Destination] = None
        self.pool = QThreadPool.globalInstance()
        self.bus = MetaBus()
        self.bus.meta.connect(self._on_meta)
        self.bus.image.connect(self._on_image)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # --- sidebar
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(260)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(22, 30, 16, 20)
        sl.setSpacing(0)
        brand = QHBoxLayout()
        brand.setSpacing(12)
        logo = label()
        logo.setPixmap(T.rounded(T.app_icon_pixmap(256), 44, 0.24))
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        t = label("Splitter<span style='color:%s'>NSP</span>" % T.BLUE)
        t.setStyleSheet("font-size: 20px; font-weight: 800;")
        names.addWidget(t)
        names.addWidget(label("Big games, FAT32 cards", "dim"))
        brand.addLayout(names)
        brand.addStretch()
        sl.addLayout(brand)
        sl.addSpacing(40)
        self.stepper = Stepper(STEPS)
        self.stepper.clicked.connect(self._go_back_to)
        sl.addWidget(self.stepper)
        sl.addStretch()
        tip = label("The 4 GB parts work with Atmosphère, DBI, Tinfoil and Awoo.",
                    "dim", wrap=True)
        sl.addWidget(tip)
        sl.addSpacing(8)
        sl.addWidget(label(f"v{__version__}", "dim"))
        h.addWidget(side)

        # --- content
        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.stack = QStackedWidget()
        self.p_games = GamesPage()
        self.p_dest = DestinationPage()
        self.p_review = ReviewPage()
        self.p_progress = ProgressPage()
        self.p_done = DonePage()
        for p in (self.p_games, self.p_dest, self.p_review, self.p_progress, self.p_done):
            self.stack.addWidget(p)
            p.changed.connect(self._update_nav)
        main.addWidget(self.stack, 1)

        self.footer = footer = QFrame()
        footer.setObjectName("footer")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(40, 14, 40, 18)
        self.btn_back = QPushButton("←  Back")
        self.btn_back.setObjectName("ghost")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.hint = label("", "dim")
        self.btn_next = GradientButton("Continue  →")
        fl.addWidget(self.btn_back)
        fl.addWidget(self.btn_cancel)
        fl.addStretch()
        fl.addWidget(self.hint)
        fl.addSpacing(14)
        fl.addWidget(self.btn_next)
        main.addWidget(footer)
        h.addLayout(main, 1)

        self.btn_back.clicked.connect(lambda: self._go(self.stack.currentIndex() - 1))
        self.btn_next.clicked.connect(self._next)
        self.btn_cancel.clicked.connect(self._cancel)
        self.p_games.add_paths.connect(self.add_paths)
        self.p_games.remove_item.connect(self._remove_item)
        self.p_done.restart.connect(self._restart)
        self._go(0, animate=False)

    # ------------------------------------------------------------------- games
    def add_paths(self, paths: List[str]):
        files: List[Path] = []
        for p in map(Path, paths):
            if p.is_dir() and p.suffix.lower() not in SUPPORTED_EXTENSIONS:
                files += sorted(f for f in p.rglob("*")
                                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
                                and not f.name.startswith("._"))
            elif p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(p)
        known = {i.path.resolve() for i in self.items}
        added = 0
        for f in files:
            if f.resolve() in known:
                continue
            try:
                item = GameItem.from_path(f)
            except OSError:
                continue
            self.items.append(item)
            known.add(f.resolve())
            self.pool.start(MetaTask(item, self.bus))
            added += 1
        if paths and not added and not files:
            QMessageBox.information(self, APP_NAME,
                                    "No NSP, NSZ or XCI files found in what you dropped.")
        self.p_games.set_items(self.items)

    def _remove_item(self, item: GameItem):
        self.items = [i for i in self.items if i is not item]
        self.p_games.set_items(self.items)

    def _on_meta(self, item: GameItem, meta: dict):
        if meta.get("name"):
            name = meta["name"]
            if item.info.kind == KIND_UPDATE:
                name += f" — {KIND_UPDATE}"
            elif item.info.kind == KIND_DLC:
                name += f" — {KIND_DLC}"
            item.name = name
        item.publisher = meta.get("publisher") or ""
        self.p_games.refresh_item(item)

    def _on_image(self, item: GameItem, kind: str, data: bytes):
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        if kind == "icon":
            item.icon = pix
        else:
            item.banner = pix
        self.p_games.refresh_item(item)

    # -------------------------------------------------------------- navigation
    def _go(self, index: int, animate: bool = True):
        index = max(0, min(index, self.stack.count() - 1))
        if index == 1:
            self.p_dest.needed = sum(i.size for i in self.items)
        if index == 2:
            self.dest = self.p_dest.destination()
            if self.dest:
                self.p_review.populate(self.items, self.dest)
        self.stack.setCurrentIndex(index)
        self.stepper.set_current(index)
        if animate:
            page = self.stack.currentWidget()
            eff = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", page)
            anim.setDuration(260)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.finished.connect(lambda: page.setGraphicsEffect(None))
            anim.start()
        self._update_nav()

    def _go_back_to(self, index: int):
        if self.stack.currentIndex() < 3:
            self._go(index)

    def _update_nav(self):
        i = self.stack.currentIndex()
        page = self.stack.currentWidget()
        self.footer.setVisible(i < 4)
        self.btn_back.setVisible(0 < i < 3)
        self.btn_cancel.setVisible(i == 3)
        self.btn_next.setVisible(i < 3)
        self.btn_next.setText("Start  ✂" if i == 2 else "Continue  →")
        self.btn_next.setEnabled(page.can_continue())
        self.stepper.locked = i >= 3
        hints = {0: "Add at least one game" if not self.items else "",
                 1: "Select a destination" if not page.can_continue() else ""}
        self.hint.setText(hints.get(i, ""))

    def _next(self):
        i = self.stack.currentIndex()
        if i == 2:
            self._start()
        else:
            self._go(i + 1)

    # -------------------------------------------------------------- processing
    def _start(self):
        dest = self.dest
        if not dest:
            return
        for it in self.items:
            it.status, it.error = "pending", ""
        self.arch_requested = self.p_review.cb_archive.isChecked() and self.p_review.cb_archive.isEnabled()
        self.eject_requested = self.p_review.cb_eject.isChecked() and self.p_review.cb_eject.isVisible()
        self.p_progress.start(self.items)
        self._go(3)
        self.worker = SplitWorker(self.items, dest, self.arch_requested, self.eject_requested)
        self.worker.item_started.connect(self._on_item_started)
        self.worker.progress.connect(self.p_progress.on_progress)
        self.worker.item_finished.connect(self._on_item_finished)
        self.worker.phase.connect(self.p_progress.on_phase)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_item_started(self, i: int):
        self.items[i].status = "running"
        self.p_progress.on_item_started(i)

    def _on_item_finished(self, i: int, ok: bool, err: str):
        self.items[i].status = "done" if ok else "error"
        self.items[i].error = err
        self.p_progress.on_item_finished(i, ok, err)

    def _cancel(self):
        if self.worker and self.worker.isRunning():
            r = QMessageBox.question(self, APP_NAME,
                                     "Cancel now? The game in progress will be removed "
                                     "from the destination.")
            if r == QMessageBox.Yes:
                self.btn_cancel.setEnabled(False)
                self.worker.cancel()

    def _on_done(self, cancelled: bool, arch_ok: bool, arch_msg: str):
        self.btn_cancel.setEnabled(True)
        self.p_done.show_result(self.items, self.dest, cancelled, self.arch_requested,
                                arch_ok, arch_msg, self.eject_requested and not cancelled)
        self._go(4)
        QApplication.alert(self)

    def _restart(self):
        self.items = []
        self.p_games.set_items([])
        self._go(0)

    def closeEvent(self, e):
        if self.worker and self.worker.isRunning():
            r = QMessageBox.question(self, APP_NAME,
                                     "Still copying. Stop and quit?")
            if r != QMessageBox.Yes:
                e.ignore()
                return
            self.worker.cancel()
            self.worker.wait(15000)
        e.accept()


def run() -> int:
    QApplication.setApplicationName(APP_NAME)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in ((QPalette.Window, T.SURFACE), (QPalette.WindowText, T.TEXT),
                        (QPalette.Base, T.SURFACE_2), (QPalette.AlternateBase, T.SURFACE),
                        (QPalette.Text, T.TEXT), (QPalette.Button, T.SURFACE_2),
                        (QPalette.ButtonText, T.TEXT), (QPalette.Highlight, T.BLUE),
                        (QPalette.HighlightedText, "#ffffff"), (QPalette.ToolTipBase, T.SURFACE_2),
                        (QPalette.ToolTipText, T.TEXT), (QPalette.PlaceholderText, T.DIM)):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setStyleSheet(T.build_stylesheet())
    app.setWindowIcon(QIcon(T.app_icon_pixmap(512)))
    win = MainWindow()
    win.show()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        win.add_paths(args)
    return app.exec()
