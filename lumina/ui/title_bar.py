"""
Lumina Player — title_bar.py
============================
Çerçevesiz pencere başlık çubuğu (40 px): logo + başlık + çalan medya adı, ortada hızlı menü,
sağda Windows hissi veren Simge Durumu / Ekranı Kapla-Geri Yükle / Kapat (hover: #E81123).
Sürükleme ve çift tıkla büyütme `startSystemMove()` ile işletim sistemine bırakılır
(Windows 11'de Aero Snap çalışır).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from lumina.ui.theme import ElidedLabel, IconButton, paint_logo, theme, ui_font


class _Logo(QWidget):
    def __init__(self, size: int = 20, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        theme.changed.connect(self.update)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self); paint_logo(p, QRectF(self.rect())); p.end()


class TitleBar(QFrame):
    openFileRequested = Signal()
    openFolderRequested = Signal()
    openUrlRequested = Signal()
    settingsRequested = Signal()

    HEIGHT = 40
    COMPACT_BELOW = 1000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(self.HEIGHT)
        self._compact = False

        # sol: logo + ad + çalan medya
        left = QWidget(); ll = QHBoxLayout(left); ll.setContentsMargins(14, 0, 8, 0); ll.setSpacing(9)
        ll.addWidget(_Logo(22))
        name = QLabel("Lumina Player"); name.setProperty("role", "heading"); name.setFont(ui_font(13, QFont.Weight.DemiBold, -0.3))
        ll.addWidget(name)
        self._sep = QLabel("•"); self._sep.setProperty("role", "caption"); self._sep.hide(); ll.addWidget(self._sep)
        self.media_title = ElidedLabel(""); self.media_title.setProperty("role", "secondary"); ll.addWidget(self.media_title, 1)

        # orta: hızlı menü
        quick = QFrame(); quick.setObjectName("QuickGroup"); quick.setFixedHeight(32)
        ql = QHBoxLayout(quick); ql.setContentsMargins(2, 2, 2, 2); ql.setSpacing(0)
        self.quick: list[IconButton] = []
        for ic, text, tip, sig in (
            ("file", "Dosya Aç", "Dosya Aç (Ctrl+O)", self.openFileRequested),
            ("folder", "Klasör Aç", "Klasör Aç (Ctrl+Shift+O)", self.openFolderRequested),
            ("link", "URL Aç", "URL / Akış Aç (Ctrl+U)", self.openUrlRequested),
            ("settings", "Ayarlar", "Ayarlar", self.settingsRequested),
        ):
            b = IconButton(ic, tip, (108 if ic != "settings" else 98, 26), 16, text=text, radius=13)
            b.clicked.connect(sig); ql.addWidget(b); self.quick.append(b)

        # sağ: pencere düğmeleri
        right = QWidget(); rl = QHBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)
        rl.addStretch(1)
        self.btn_min = IconButton("win_min", "Simge durumuna küçült", (46, self.HEIGHT), 18, variant="titlebar")
        self.btn_max = IconButton("win_max", "Ekranı kapla", (46, self.HEIGHT), 18, variant="titlebar")
        self.btn_close = IconButton("win_close", "Kapat", (46, self.HEIGHT), 18, variant="close")
        self.btn_min.clicked.connect(lambda: self.window().showMinimized())
        self.btn_max.clicked.connect(self.toggle_maximize)
        self.btn_close.clicked.connect(lambda: self.window().close())
        for b in (self.btn_min, self.btn_max, self.btn_close): rl.addWidget(b)

        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        lay.addWidget(left, 1); lay.addWidget(quick, 0); lay.addWidget(right, 1)

    def set_media_title(self, text: str) -> None:
        self.media_title.setText(text); self._sep.setVisible(bool(text))

    def toggle_maximize(self) -> None:
        w = self.window()
        w.showNormal() if w.isMaximized() else w.showMaximized()

    def _sync_max_icon(self) -> None:
        mx = self.window().isMaximized()
        self.btn_max.set_icon_name("win_restore" if mx else "win_max")
        self.btn_max.setToolTip("Geri yükle" if mx else "Ekranı kapla")

    def showEvent(self, e) -> None:  # noqa: N802
        self.window().installEventFilter(self); self._sync_max_icon(); super().showEvent(e)

    def eventFilter(self, obj, ev) -> bool:  # noqa: N802
        if obj is self.window() and ev.type() == QEvent.Type.WindowStateChange:
            self._sync_max_icon()
        return False

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        compact = self.width() < self.COMPACT_BELOW
        if compact != self._compact:
            self._compact = compact
            for b in self.quick:
                b.set_show_text(not compact, collapsed_width=34)

    # sürükleme + çift tıkla büyütme
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            h = self.window().windowHandle()
            if h is not None:
                h.startSystemMove(); e.accept(); return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximize(); e.accept()
