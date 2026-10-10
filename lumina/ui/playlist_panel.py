"""
Lumina Player — playlist_panel.py
=================================
Sağdan akıcı biçimde açılıp kapanan 360 px'lik gelişmiş çalma listesi paneli.

* MediaItem / PlaylistModel   : veri katmanı (doğal sıralama, ilerleme, süre, çözünürlük)
* PlaylistItemDelegate        : QPainter ile piksel hassasiyetli satır çizimi;
                                başlık `QFontMetrics.elidedText` ile, sağdaki süre ve rozete
                                ASLA taşmayacak şekilde hesaplanır
* FolderScanner               : arka plan iş parçacığında canlı klasör taraması
* PlaylistPanel               : başlık, mod düğmeleri, arama, sıralama/dışa aktarma, banner,
                                tarama çubuğu, boş durum, alt bilgi
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    Property, QAbstractListModel, QPointF, QEasingCurve, QModelIndex, QPoint, QPropertyAnimation, QRectF,
    QRect, QSize, QSortFilterProxyModel, Qt, QThread, QTimer, QVariantAnimation, Signal,
)
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QPushButton,
    QStackedWidget, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from lumina.ui.theme import (
    ElidedLabel, IconButton, format_hms, icon, icon_pixmap, make_menu, mix, populate_choice_menu,
    theme, tile_colors, ui_font, with_alpha,
)

VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
             ".ts", ".m2ts", ".3gp", ".ogv"}
AUDIO_EXT = {".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".aiff", ".alac"}

ITEM_ROLE = Qt.ItemDataRole.UserRole + 1
CURRENT_ROLE = Qt.ItemDataRole.UserRole + 2
NUMBER_ROLE = Qt.ItemDataRole.UserRole + 3


def natural_key(text: str) -> list:
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", text)]


def fold(text: str) -> str:
    """Büyük/küçük harf ve aksan duyarsız (İ/ı dahil) arama anahtarı."""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t.casefold().replace("ı", "i")


def resolution_label(height: int) -> str:
    if height >= 4320: return "8K"
    if height >= 2160: return "4K"
    if height > 0: return f"{height}p"
    return ""


def human_size(n: int) -> str:
    v = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024 or unit == "TB":
            return f"{v:.0f} {unit}" if unit == "B" else f"{v:.1f} {unit}"
        v /= 1024
    return f"{n} B"


from lumina.core.media_item import MediaItem


# ─────────────────────────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────────────────────────
class PlaylistModel(QAbstractListModel):
    changedTotals = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.items: list[MediaItem] = []
        self.current = -1

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.items)):
            return None
        it = self.items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole: return it.title
        if role == ITEM_ROLE: return it
        if role == CURRENT_ROLE: return index.row() == self.current
        if role == NUMBER_ROLE: return index.row() + 1
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{it.title}\n{it.path}" + (f"\n{human_size(it.size)}" if it.size else "")
        return None

    def add_items(self, new: list[MediaItem]) -> None:
        if not new: return
        start = len(self.items)
        self.beginInsertRows(QModelIndex(), start, start + len(new) - 1)
        self.items.extend(new)
        self.endInsertRows()
        self.changedTotals.emit()

    def clear(self) -> None:
        self.beginResetModel(); self.items.clear(); self.current = -1; self.endResetModel()
        self.changedTotals.emit()

    def remove_rows(self, rows: list[int]) -> None:
        cur_item = self.items[self.current] if 0 <= self.current < len(self.items) else None
        self.beginResetModel()
        for r in sorted(set(rows), reverse=True):
            if 0 <= r < len(self.items):
                del self.items[r]
        self.current = next((i for i, it in enumerate(self.items) if it is cur_item), -1) if cur_item else -1
        self.endResetModel()
        self.changedTotals.emit()

    def set_current(self, row: int) -> None:
        old, self.current = self.current, row
        for r in (old, row):
            if 0 <= r < len(self.items):
                self.dataChanged.emit(self.index(r), self.index(r))

    def update_item(self, row: int, **fields) -> None:
        if 0 <= row < len(self.items):
            for k, v in fields.items():
                setattr(self.items[row], k, v)
            self.dataChanged.emit(self.index(row), self.index(row))
            self.changedTotals.emit()

    def sort_by(self, key: str, reverse: bool = False) -> None:
        keyf = {
            "name": lambda it: natural_key(it.title),
            "date": lambda it: it.mtime,
            "size": lambda it: it.size,
        }[key]
        cur = self.items[self.current] if 0 <= self.current < len(self.items) else None
        self.layoutAboutToBeChanged.emit()
        self.items.sort(key=keyf, reverse=reverse)
        self.current = next((i for i, it in enumerate(self.items) if it is cur), -1) if cur else -1
        self.layoutChanged.emit()

    def reverse(self) -> None:
        cur = self.items[self.current] if 0 <= self.current < len(self.items) else None
        self.layoutAboutToBeChanged.emit()
        self.items.reverse()
        self.current = next((i for i, it in enumerate(self.items) if it is cur), -1) if cur else -1
        self.layoutChanged.emit()

    def total_seconds(self) -> int:
        return sum(it.duration for it in self.items)


class FilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._q = ""

    def set_query(self, q: str) -> None:
        self._q = fold(q.strip())
        self.invalidateFilter()

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:  # noqa: N802
        if not self._q: return True
        it: MediaItem = self.sourceModel().items[row]
        return self._q in fold(it.title) or self._q in fold(it.ext)


# ─────────────────────────────────────────────────────────────────────────────
# Delege: piksel hassasiyetli satır çizimi
# ─────────────────────────────────────────────────────────────────────────────
class PlaylistItemDelegate(QStyledItemDelegate):
    ROW_HEIGHT = 64
    H_PAD = 10            # kart içi yatay boşluk
    TILE = 40             # sol kapak karosu
    COL_GAP = 12          # sütunlar arası boşluk
    RADIUS = 10

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.phase = 0.0
        self.playing = False

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    # -- yerleşim: boyama ve test için tek yerden hesaplanır ----------------------
    def layout_for(self, card: QRectF, item: MediaItem) -> dict:
        f_title, f_sub = ui_font(13, QFont.Weight.DemiBold, -0.2), ui_font(11)
        f_dur, f_badge, f_idx = ui_font(12, QFont.Weight.Medium), ui_font(10, QFont.Weight.Bold, 0.3), ui_font(12, QFont.Weight.DemiBold)
        fm_t, fm_s, fm_d = QFontMetrics(f_title), QFontMetrics(f_sub), QFontMetrics(f_dur)
        fm_b, fm_i = QFontMetrics(f_badge), QFontMetrics(f_idx)
        inner = card.adjusted(self.H_PAD, 0, -self.H_PAD, 0)
        idx_w = self.TILE
        dur_text = format_hms(item.duration) if item.duration > 0 else "--:--"
        dur_w = fm_d.horizontalAdvance(dur_text)
        badge_w = fm_b.horizontalAdvance(item.resolution) + 16 if item.resolution else 0
        right_w = max(dur_w, badge_w)
        right_x = inner.right() - right_w
        text_x = inner.left() + idx_w + self.COL_GAP
        text_w = max(0.0, right_x - self.COL_GAP - text_x)
        block_h = fm_t.height() + 3 + fm_s.height()
        y0 = card.center().y() - block_h / 2 - 1
        return dict(
            f_title=f_title, f_sub=f_sub, f_dur=f_dur, f_badge=f_badge, f_idx=f_idx,
            fm_t=fm_t, fm_s=fm_s, fm_d=fm_d, fm_b=fm_b,
            idx_rect=QRectF(inner.left(), card.center().y() - self.TILE / 2 - 1, idx_w, self.TILE),
            title_rect=QRect(int(text_x), int(y0), int(text_w), fm_t.height()),
            sub_rect=QRect(int(text_x), int(y0 + fm_t.height() + 3), int(text_w), fm_s.height()),
            dur_rect=QRect(int(right_x), int(y0), int(right_w), fm_t.height()),
            badge_rect=QRectF(inner.right() - badge_w, y0 + fm_t.height() + 3 + (fm_s.height() - 17) / 2, badge_w, 17),
            dur_text=dur_text,
        )

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:  # noqa: N802
        item: MediaItem | None = index.data(ITEM_ROLE)
        if item is None:
            return
        pal, acc = theme.p, theme.accent
        is_cur = bool(index.data(CURRENT_ROLE))
        number = index.data(NUMBER_ROLE)
        st = option.state
        hover = bool(st & QStyle.StateFlag.State_MouseOver)
        selected = bool(st & QStyle.StateFlag.State_Selected)

        painter.save()
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        card = QRectF(option.rect).adjusted(6, 3, -6, -3)
        L = self.layout_for(card, item)

        # arka plan
        if is_cur:      # soldan sağa sönen vurgu ışığı
            gbg = QLinearGradient(card.topLeft(), card.topRight())
            gbg.setColorAt(0, with_alpha(acc, 58 if hover else 50)); gbg.setColorAt(1, with_alpha(acc, 14))
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(gbg))
            painter.drawRoundedRect(card, self.RADIUS, self.RADIUS)
            painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(with_alpha(acc, 64), 1))
            painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), self.RADIUS, self.RADIUS)
        elif selected or hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(pal.active) if selected else with_alpha(pal.text, 12 if theme.mode == "dark" else 9))
            painter.drawRoundedRect(card, self.RADIUS, self.RADIUS)

        # sol sütun: kapak karosu (sıra numarası) ya da çalarken ışıyan ekolayzır
        ir: QRectF = L["idx_rect"]
        self._paint_tile(painter, ir, item, number, is_cur)

        # orta sütun: başlık (kısaltılmış) + tür satırı
        painter.setFont(L["f_title"])
        painter.setPen(theme.accent_text if is_cur else QColor(pal.text))
        tr: QRect = L["title_rect"]
        painter.drawText(tr, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         L["fm_t"].elidedText(item.title, Qt.TextElideMode.ElideRight, tr.width()))
        painter.setFont(L["f_sub"]); painter.setPen(QColor(pal.text2))
        sr: QRect = L["sub_rect"]
        painter.drawText(sr, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         L["fm_s"].elidedText(item.type_line, Qt.TextElideMode.ElideRight, sr.width()))

        # sağ sütun: süre + çözünürlük rozeti
        painter.setFont(L["f_dur"]); painter.setPen(QColor(pal.text2))
        painter.drawText(L["dur_rect"], Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, L["dur_text"])
        if item.resolution:
            self._paint_badge(painter, L["badge_rect"], item.resolution, L["f_badge"])

        # alt çizgi: izleme ilerlemesi (2 px)
        if 0.0 < item.progress < 1.0:
            x0, x1 = card.left() + self.RADIUS, card.right() - self.RADIUS
            y = card.bottom() - 3
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(with_alpha(pal.text, 34)); painter.drawRoundedRect(QRectF(x0, y, x1 - x0, 2), 1, 1)
            painter.setBrush(acc); painter.drawRoundedRect(QRectF(x0, y, (x1 - x0) * item.progress, 2), 1, 1)
        painter.restore()

    def _paint_tile(self, p: QPainter, r: QRectF, item: MediaItem, number: int, is_cur: bool) -> None:
        acc = theme.accent
        rad = 11
        if is_cur:
            glow = QRadialGradient(r.center(), r.width() * 0.95)
            glow.setColorAt(0.4, with_alpha(acc, 90)); glow.setColorAt(1, with_alpha(acc, 0))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(glow)); p.drawEllipse(r.center(), r.width() * 0.95, r.width() * 0.95)
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, mix(acc, "#FFFFFF", 0.14)); g.setColorAt(1, mix(acc, theme.accent_alt, 0.5))
            p.setBrush(QBrush(g)); p.drawRoundedRect(r, rad, rad)
            self._paint_equalizer(p, r, theme.on_accent)
            return
        c1, c2 = tile_colors(item.title)
        g = QLinearGradient(r.topLeft(), r.bottomRight()); g.setColorAt(0, c1); g.setColorAt(1, c2)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawRoundedRect(r, rad, rad)
        hl = QRadialGradient(QPointF(r.left() + r.width() * 0.25, r.top() + r.height() * 0.1), r.width())
        hl.setColorAt(0, QColor(255, 255, 255, 70)); hl.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hl)); p.drawRoundedRect(r, rad, rad)
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), rad, rad)
        p.setFont(ui_font(12, QFont.Weight.DemiBold)); p.setPen(QColor(255, 255, 255, 240))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, f"{number:02d}")

    def _paint_badge(self, p: QPainter, r: QRectF, text: str, font: QFont) -> None:
        pal, acc = theme.p, theme.accent
        p.setPen(Qt.PenStyle.NoPen)
        if text in ("4K", "8K"):
            g = QLinearGradient(r.topLeft(), r.topRight()); g.setColorAt(0, acc); g.setColorAt(1, mix(acc, theme.accent_alt, 0.7))
            p.setBrush(QBrush(g)); fg = theme.on_accent
        elif text in ("1080p", "1440p"):
            p.setBrush(with_alpha(acc, 40)); fg = theme.accent_text
        else:
            p.setBrush(with_alpha(pal.text, 20)); fg = QColor(pal.text2)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setFont(font); p.setPen(fg)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_equalizer(self, p: QPainter, r: QRectF, color: QColor) -> None:
        bars, w, gap, maxh = 3, 3.4, 2.8, 16.0
        total = bars * w + (bars - 1) * gap
        x = r.center().x() - total / 2
        base = r.center().y() + maxh / 2
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(color)
        for i in range(bars):
            h = 5 + 11 * abs(math.sin(self.phase + i * 1.25)) if self.playing else (6, 12, 8)[i]
            p.drawRoundedRect(QRectF(x + i * (w + gap), base - h, w, h), 1.4, 1.4)


# ─────────────────────────────────────────────────────────────────────────────
# Klasör tarayıcı
# ─────────────────────────────────────────────────────────────────────────────
class FolderScanner(QThread):
    batch = Signal(list)        # list[MediaItem]
    progress = Signal(int)      # şimdiye kadar bulunan
    scanned = Signal(int, bool)  # toplam, iptal_edildi_mi

    def __init__(self, folder: str, recursive: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.folder, self.recursive = folder, recursive

    def run(self) -> None:
        found, buf = 0, []
        for root, dirs, files in os.walk(self.folder):
            if self.isInterruptionRequested():
                self.scanned.emit(found, True); return
            dirs.sort(key=natural_key)
            if not self.recursive:
                dirs.clear()
            for name in sorted(files, key=natural_key):
                if Path(name).suffix.lower() in VIDEO_EXT | AUDIO_EXT:
                    buf.append(MediaItem.from_path(os.path.join(root, name)))
                    found += 1
                    if len(buf) >= 20:
                        self.batch.emit(buf); buf = []
                        self.progress.emit(found)
        if buf:
            self.batch.emit(buf)
        self.progress.emit(found)
        self.scanned.emit(found, False)


class ScanBar(QWidget):
    """İnce, sonsuz kayan vurgu çizgisi (belirsiz ilerleme)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)
        self._t = 0.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1100, loopCount=-1)
        self._anim.valueChanged.connect(self._tick)

    def _tick(self, v) -> None:
        self._t = float(v); self.update()

    def showEvent(self, e) -> None:  # noqa: N802
        self._anim.start(); super().showEvent(e)

    def hideEvent(self, e) -> None:  # noqa: N802
        self._anim.stop(); super().hideEvent(e)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(with_alpha(theme.accent, 36))
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        seg = w * 0.38
        x = -seg + (w + seg) * self._t
        p.setClipRect(QRectF(0, 0, w, h))
        p.setBrush(theme.accent); p.drawRoundedRect(QRectF(x, 0, seg, h), h / 2, h / 2)
        p.end()


class SearchBox(QLineEdit):
    """Anlık filtreleyen arama kutusu; tek tıkla temizleme düğmeli."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchBox")
        self.setPlaceholderText("Listede ara…")
        self._lead = QAction(self)
        self._clear = QAction(self)
        self._clear.setToolTip("Temizle")
        self.addAction(self._lead, QLineEdit.ActionPosition.LeadingPosition)
        self.addAction(self._clear, QLineEdit.ActionPosition.TrailingPosition)
        self._clear.triggered.connect(self.clear)
        self.textChanged.connect(lambda t: self._clear.setVisible(bool(t)))
        self._clear.setVisible(False)
        theme.changed.connect(self._refresh_icons)
        self._refresh_icons()

    def _refresh_icons(self) -> None:
        self._lead.setIcon(icon("search", theme.p.muted, 16))
        self._clear.setIcon(icon("close", theme.p.text2, 16))


class EmptyState(QWidget):
    addFilesRequested = Signal()
    addFolderRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tile = QFrame(); self.tile.setObjectName("IconTile"); self.tile.setFixedSize(76, 76)
        self.glyph = QLabel(self.tile); self.glyph.setGeometry(0, 0, 76, 76); self.glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel("Çalma Listesi Boş"); self.title.setProperty("role", "title")
        self.hint = QLabel("Dosya veya klasör sürükleyip bırakın\nya da aşağıdan ekleyin.")
        self.hint.setProperty("role", "caption"); self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_files = QPushButton("Dosya Ekle"); self.btn_files.setProperty("variant", "primary")
        self.btn_folder = QPushButton("Klasör Aç")
        for b in (self.btn_files, self.btn_folder):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_files.clicked.connect(self.addFilesRequested)
        self.btn_folder.clicked.connect(self.addFolderRequested)
        row = QHBoxLayout(); row.setSpacing(8); row.addStretch(1); row.addWidget(self.btn_files); row.addWidget(self.btn_folder); row.addStretch(1)
        lay = QVBoxLayout(self); lay.setContentsMargins(24, 0, 24, 40); lay.setSpacing(6)
        lay.addStretch(1)
        lay.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignHCenter); lay.addSpacing(10)
        lay.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.hint); lay.addSpacing(10); lay.addLayout(row); lay.addStretch(2)
        theme.changed.connect(lambda: self.set_mode(self._filtered))
        self._filtered = False
        self.set_mode(False)

    def set_mode(self, filtered: bool) -> None:
        self._filtered = filtered
        self.glyph.setPixmap(icon_pixmap("search" if filtered else "video", theme.accent, 32))
        self.title.setText("Sonuç bulunamadı" if filtered else "Çalma Listesi Boş")
        self.hint.setText("Farklı bir arama deneyin." if filtered else "Dosya veya klasör sürükleyip bırakın\nya da aşağıdan ekleyin.")
        self.btn_files.setVisible(not filtered); self.btn_folder.setVisible(not filtered)


# ─────────────────────────────────────────────────────────────────────────────
# Panel
# ─────────────────────────────────────────────────────────────────────────────
class PlaylistPanel(QFrame):
    PANEL_WIDTH = 360

    itemActivated = Signal(int, object)      # kaynak satır, MediaItem
    closeRequested = Signal()
    playModeChanged = Signal(str)            # "sequential" | "shuffle" | "repeat"
    addFilesRequested = Signal()
    addFolderRequested = Signal()
    pathsDropped = Signal(list)
    cleared = Signal()
    openChanged = Signal(bool)

    def __init__(self, parent: QWidget | None = None, *, opened: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("SidePanel")
        self.setAcceptDrops(True)
        self._open = opened
        self._width = self.PANEL_WIDTH if opened else 0
        self._mode = "sequential"
        self._history: list[int] = []
        self._scanner: FolderScanner | None = None
        self._folder_name = ""

        self.model = PlaylistModel(self)
        self.proxy = FilterProxy(self); self.proxy.setSourceModel(self.model)
        self.delegate = PlaylistItemDelegate(self)

        self._content = QWidget(self); self._content.setObjectName("PlaylistContent")
        self._content.setFixedWidth(self.PANEL_WIDTH)
        root = QVBoxLayout(self._content); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── başlık ──────────────────────────────────────────────────────────────
        head = QHBoxLayout(); head.setContentsMargins(18, 16, 12, 10); head.setSpacing(8)
        title = QLabel("Çalma Listesi"); title.setProperty("role", "title")
        self.badge = QLabel("0 Video"); self.badge.setObjectName("CountBadge")
        head.addWidget(title); head.addWidget(self.badge); head.addStretch(1)
        self.mode_buttons: dict[str, IconButton] = {}
        seg = QFrame(); seg.setObjectName("SegGroup"); seg.setFixedHeight(32)
        sl = QHBoxLayout(seg); sl.setContentsMargins(2, 2, 2, 2); sl.setSpacing(2)
        for key, ic, tip in (("sequential", "sequential", "Sırayla"), ("shuffle", "shuffle", "Karışık (Shuffle)"),
                             ("repeat", "repeat", "Tekrar")):
            b = IconButton(ic, tip, (28, 26), 16, checkable=True, radius=10)
            b.clicked.connect(lambda _=False, k=key: self.set_play_mode(k))
            self.mode_buttons[key] = b; sl.addWidget(b)
        head.addWidget(seg)
        head.addSpacing(2)
        self.btn_close = IconButton("close", "Paneli kapat (P)", 28, 16)
        self.btn_close.clicked.connect(self.closeRequested)
        head.addWidget(self.btn_close)
        root.addLayout(head)

        # ── arama + sıralama + dışa aktarma ────────────────────────────────────────
        tools = QHBoxLayout(); tools.setContentsMargins(14, 0, 12, 10); tools.setSpacing(4)
        self.search = SearchBox(); self.search.textChanged.connect(self._on_filter)
        self.btn_sort = IconButton("sort", "Sırala", 38, 18, radius=12); self.btn_export = IconButton("export", "Dışa aktar", 38, 18, radius=12)
        self.sort_menu, self.export_menu = make_menu(self), make_menu(self)
        self.btn_sort.attach_menu(self.sort_menu); self.btn_export.attach_menu(self.export_menu)
        self._sort_key = ""
        self._build_menus()
        tools.addWidget(self.search, 1); tools.addWidget(self.btn_sort); tools.addWidget(self.btn_export)
        root.addLayout(tools)

        # ── klasör banner'ı + canlı tarama ──────────────────────────────────────────
        self.banner = QFrame(); self.banner.setObjectName("FolderBanner")
        bl = QHBoxLayout(self.banner); bl.setContentsMargins(12, 8, 12, 8)
        self.banner_label = ElidedLabel(); bl.addWidget(self.banner_label)
        self.banner.hide()
        bwrap = QVBoxLayout(); bwrap.setContentsMargins(12, 0, 12, 8); bwrap.addWidget(self.banner)
        root.addLayout(bwrap)

        self.scan_box = QWidget(); sb = QVBoxLayout(self.scan_box); sb.setContentsMargins(16, 0, 16, 8); sb.setSpacing(5)
        self.scan_bar = ScanBar(); self.scan_label = QLabel("Taranıyor… 0 dosya bulundu"); self.scan_label.setProperty("role", "caption")
        sb.addWidget(self.scan_bar); sb.addWidget(self.scan_label); self.scan_box.hide()
        root.addWidget(self.scan_box)

        # ── liste / boş durum ───────────────────────────────────────────────────────────
        self.view = QListView(); self.view.setObjectName("PlaylistList")
        self.view.setModel(self.proxy); self.view.setItemDelegate(self.delegate)
        self.view.setUniformItemSizes(True); self.view.setMouseTracking(True)
        self.view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.view.doubleClicked.connect(self._on_double_click)
        self.view.setAcceptDrops(False)
        self.empty = EmptyState()
        self.empty.addFilesRequested.connect(self.addFilesRequested)
        self.empty.addFolderRequested.connect(self.addFolderRequested)
        self.stack = QStackedWidget(); self.stack.addWidget(self.view); self.stack.addWidget(self.empty)
        root.addWidget(self.stack, 1)

        # ── alt bilgi ─────────────────────────────────────────────────────────────────────
        line = QFrame(); line.setProperty("role", "divider"); line.setFixedHeight(1); root.addWidget(line)
        foot = QHBoxLayout(); foot.setContentsMargins(16, 8, 12, 8)
        self.total_label = QLabel("Toplam süre: 00:00:00"); self.total_label.setProperty("role", "caption")
        self.btn_clear = IconButton("trash", "Listedeki tüm öğeleri kaldır", (132, 30), 16, variant="danger", text="Listeyi Temizle")
        self.btn_clear.clicked.connect(self.clear_playlist)
        foot.addWidget(self.total_label, 1); foot.addWidget(self.btn_clear)
        root.addLayout(foot)

        # ── bağlantılar ──────────────────────────────────────────────────────────────────
        self.model.changedTotals.connect(self._update_summary)
        self.model.rowsInserted.connect(lambda *_: self._update_stack())
        self.model.modelReset.connect(self._update_stack)
        self.proxy.rowsInserted.connect(lambda *_: self._update_stack())
        self.proxy.rowsRemoved.connect(lambda *_: self._update_stack())
        self.proxy.layoutChanged.connect(self._update_stack)
        self.proxy.modelReset.connect(self._update_stack)
        self._eq_timer = QTimer(self); self._eq_timer.setInterval(90); self._eq_timer.timeout.connect(self._tick_eq)
        theme.changed.connect(self._on_theme)

        self._anim = QPropertyAnimation(self, b"panelWidth", self)
        self._anim.setDuration(260); self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.finished.connect(self._anim_done)
        self.set_play_mode("sequential")
        self._apply_width(self._width)
        self._update_summary(); self._update_stack()

    # ── animasyonlu açılıp kapanma ───────────────────────────────────────────────
    def _get_w(self) -> int: return self._width

    def _apply_width(self, w: int) -> None:
        self._width = int(w)
        self.setFixedWidth(self._width)
        self.setVisible(self._width > 0)

    panelWidth = Property(int, _get_w, _apply_width)

    def is_open(self) -> bool: return self._open

    def set_open(self, on: bool, animated: bool = True) -> None:
        if on == self._open and self._anim.state() != QPropertyAnimation.State.Running:
            return
        self._open = on
        target = self.PANEL_WIDTH if on else 0
        self._anim.stop()
        if not animated:
            self._apply_width(target); self.openChanged.emit(on); return
        self.setVisible(True)
        self._anim.setStartValue(self._width); self._anim.setEndValue(target); self._anim.start()
        self.openChanged.emit(on)

    def toggle(self) -> None:
        self.set_open(not self._open)

    def _anim_done(self) -> None:
        self.setVisible(self._width > 0)

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._content.setGeometry(self.width() - self.PANEL_WIDTH, 0, self.PANEL_WIDTH, self.height())

    # ── içerik API'si ──────────────────────────────────────────────────────────────
    def add_paths(self, paths: list[str]) -> None:
        files = [p for p in paths if os.path.isfile(p) and Path(p).suffix.lower() in VIDEO_EXT | AUDIO_EXT]
        self.model.add_items([MediaItem.from_path(p) for p in files])
        for d in (p for p in paths if os.path.isdir(p)):
            self.load_folder(d, replace=False)

    def add_items(self, items: list[MediaItem]) -> None:
        self.model.add_items(items)

    def clear_playlist(self) -> None:
        self.cancel_scan(); self.model.clear(); self._history.clear()
        self.banner.hide(); self.scan_box.hide()
        self.cleared.emit()

    def current_row(self) -> int: return self.model.current

    def current_item(self) -> MediaItem | None:
        c = self.model.current
        return self.model.items[c] if 0 <= c < len(self.model.items) else None

    def set_current(self, row: int) -> None:
        self.model.set_current(row)
        if 0 <= row < len(self.model.items):
            ix = self.proxy.mapFromSource(self.model.index(row))
            if ix.isValid():
                self.view.scrollTo(ix, QListView.ScrollHint.EnsureVisible)

    def activate(self, row: int) -> None:
        if not (0 <= row < len(self.model.items)):
            return
        if self.model.current >= 0 and self.model.current != row:
            self._history.append(self.model.current)
        self.set_current(row)
        self.itemActivated.emit(row, self.model.items[row])

    def set_playing(self, on: bool) -> None:
        self.delegate.playing = on
        if on and self._open:
            self._eq_timer.start()
        else:
            self._eq_timer.stop()
        self._repaint_current()

    def next_row(self) -> int:
        n, cur = len(self.model.items), self.model.current
        if n == 0: return -1
        if self._mode == "shuffle":
            pool = [i for i in range(n) if i != cur]
            return random.choice(pool) if pool else cur
        if cur + 1 < n: return cur + 1
        return 0 if self._mode == "repeat" else -1

    def previous_row(self) -> int:
        n, cur = len(self.model.items), self.model.current
        if n == 0: return -1
        if self._mode == "shuffle" and self._history:
            return self._history.pop()
        if cur - 1 >= 0: return cur - 1
        return n - 1 if self._mode == "repeat" else -1

    def play_next(self) -> None:
        r = self.next_row()
        if r >= 0: self.activate(r)

    def play_previous(self) -> None:
        r = self.previous_row()
        if r >= 0:
            self.set_current(r); self.itemActivated.emit(r, self.model.items[r])

    def update_item(self, row: int, **fields) -> None:
        self.model.update_item(row, **fields)

    def set_progress(self, row: int, ratio: float) -> None:
        self.model.update_item(row, progress=max(0.0, min(1.0, float(ratio))))

    def set_play_mode(self, mode: str) -> None:
        self._mode = mode
        for k, b in self.mode_buttons.items():
            b.setChecked(k == mode)
        self.playModeChanged.emit(mode)

    # ── klasör tarama ──────────────────────────────────────────────────────────────
    def load_folder(self, path: str, *, replace: bool = True, recursive: bool = True) -> None:
        self.cancel_scan()
        if replace:
            self.model.clear(); self._history.clear()
        self._folder_name = os.path.basename(os.path.normpath(path)) or path
        self._scan_base = len(self.model.items)
        self.banner_label.setText(f"📁  Klasör: {self._folder_name} (0 dosya)"); self.banner.show()
        self.scan_label.setText("Taranıyor… 0 dosya bulundu"); self.scan_box.show()
        sc = FolderScanner(path, recursive, self)
        sc.batch.connect(self.model.add_items)
        sc.progress.connect(self._on_scan_progress)
        sc.scanned.connect(self._on_scan_done)
        self._scanner = sc; sc.start()

    def cancel_scan(self) -> None:
        sc = self._scanner
        if sc is not None:
            self._scanner = None
            for sig in (sc.batch, sc.progress, sc.scanned):
                try: sig.disconnect()
                except (RuntimeError, TypeError): pass
            sc.requestInterruption(); sc.wait(2000)
        self.scan_box.hide()

    def _on_scan_progress(self, n: int) -> None:
        self.scan_label.setText(f"Taranıyor… {n} dosya bulundu")
        self.banner_label.setText(f"📁  Klasör: {self._folder_name} ({n} dosya)")

    def _on_scan_done(self, total: int, cancelled: bool) -> None:
        self.scan_box.hide()
        self.banner_label.setText(f"📁  Klasör: {self._folder_name} ({total} dosya)")
        self._scanner = None

    # ── sıralama / dışa aktarma ────────────────────────────────────────────────────
    def _build_menus(self) -> None:
        entries = [("A → Z (Doğal Sıralama)", "name"), ("Tarihe Göre (Yeni → Eski)", "date"),
                   ("Boyuta Göre (Büyük → Küçük)", "size")]
        populate_choice_menu(self.sort_menu, entries, self._sort_key, self._sort)
        self.sort_menu.addSeparator()
        self.sort_menu.addAction("Sırayı Ters Çevir").triggered.connect(self.model.reverse)
        self.export_menu.clear()
        self.export_menu.addAction("M3U olarak kaydet…").triggered.connect(lambda: self._export("m3u"))
        self.export_menu.addAction("JSON olarak kaydet…").triggered.connect(lambda: self._export("json"))

    def _sort(self, key) -> None:
        self._sort_key = key
        self.model.sort_by(key, reverse=key in ("date", "size"))
        self._build_menus()

    def _export(self, fmt: str) -> None:
        if not self.model.items: return
        flt = "M3U Çalma Listesi (*.m3u8 *.m3u)" if fmt == "m3u" else "JSON (*.json)"
        path, _ = QFileDialog.getSaveFileName(self, "Çalma listesini kaydet", f"lumina-liste.{'m3u8' if fmt == 'm3u' else 'json'}", flt)
        if path:
            (self.export_m3u if fmt == "m3u" else self.export_json)(path)

    def export_m3u(self, path: str) -> None:
        lines = ["#EXTM3U"]
        for it in self.model.items:
            lines += [f"#EXTINF:{it.duration if it.duration else -1},{it.title}", it.path]
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def export_json(self, path: str) -> None:
        data = [dict(path=i.path, title=i.title, kind=i.kind, duration=i.duration, resolution=i.resolution,
                     size=i.size, progress=i.progress) for i in self.model.items]
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── iç mantık ───────────────────────────────────────────────────────────────────────
    def _on_filter(self, text: str) -> None:
        self.proxy.set_query(text)
        self._update_stack()

    def _update_stack(self) -> None:
        has_items = len(self.model.items) > 0
        visible = self.proxy.rowCount() > 0
        self.empty.set_mode(has_items and not visible)
        self.stack.setCurrentWidget(self.view if visible else self.empty)

    def _update_summary(self) -> None:
        items = self.model.items
        n = len(items)
        videos = sum(1 for i in items if i.kind == "video")
        word = "Video" if videos == n else ("Ses" if videos == 0 else "Medya")
        self.badge.setText(f"{n} {word}")
        self.total_label.setText(f"Toplam süre: {format_hms(self.model.total_seconds())}")
        self.btn_clear.setEnabled(n > 0)

    def _on_double_click(self, ix) -> None:
        self.activate(self.proxy.mapToSource(ix).row())

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if self.view.hasFocus():
            if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.view.currentIndex().isValid():
                self._on_double_click(self.view.currentIndex()); return
            if e.key() == Qt.Key.Key_Delete:
                self._remove_selected(); return
        super().keyPressEvent(e)

    def _selected_rows(self) -> list[int]:
        return [self.proxy.mapToSource(i).row() for i in self.view.selectionModel().selectedIndexes()]

    def _remove_selected(self) -> None:
        rows = self._selected_rows()
        if rows: self.model.remove_rows(rows)

    def _context_menu(self, pos: QPoint) -> None:
        ix = self.view.indexAt(pos)
        if not ix.isValid(): return
        if not self.view.selectionModel().isSelected(ix):
            self.view.setCurrentIndex(ix)
        m = make_menu(self)
        m.addAction("Oynat").triggered.connect(lambda: self._on_double_click(ix))
        m.addAction("Listeden Kaldır").triggered.connect(self._remove_selected)
        m.exec(self.view.viewport().mapToGlobal(pos))

    def _tick_eq(self) -> None:
        self.delegate.phase += 0.55
        self._repaint_current()

    def _repaint_current(self) -> None:
        c = self.model.current
        if c >= 0:
            ix = self.proxy.mapFromSource(self.model.index(c))
            if ix.isValid():
                self.view.viewport().update(self.view.visualRect(ix))

    def _on_theme(self) -> None:
        self._build_menus()
        self.view.viewport().update()

    # ── sürükle-bırak ────────────────────────────────────────────────────────────────────
    def dragEnterEvent(self, e) -> None:  # noqa: N802
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e) -> None:  # noqa: N802
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.add_paths(paths); self.pathsDropped.emit(paths); e.acceptProposedAction()
