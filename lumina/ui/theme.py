"""
Lumina Player — theme.py
========================
Tek kaynaklı tasarım sistemi: renk paleti (Koyu/Açık), dinamik vurgu rengi, QSS,
vektörel ikon seti (QPainter) ve tüm modüllerin paylaştığı küçük bileşenler.

Kullanım::

    from theme import theme
    app = QApplication([])
    theme.set_accent("Purple")      # Blue | Purple | Red | Green | Orange | "#RRGGBB"
    theme.set_mode("dark")          # dark | light
    theme.apply(app)                # yazı tipi + uygulama stil sayfası

Özel çizim yapan widget'lar `theme.changed` sinyaline bağlanır ve `theme.p`
(palet) ile `theme.accent` (QColor) üzerinden okur; böylece vurgu rengi veya
tema değiştiğinde anında güncellenir.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass
from functools import lru_cache
from string import Template
from typing import Callable, Sequence

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction, QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QPolygonF, QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication, QLabel, QMenu, QSizePolicy, QToolButton, QWidget,
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Renkler
# ─────────────────────────────────────────────────────────────────────────────
ACCENTS: dict[str, str] = {
    "Blue": "#4C8DFF",
    "Purple": "#8B6CFF",
    "Red": "#FF4D6A",
    "Green": "#22C55E",
    "Orange": "#FF8A3D",
}
DANGER = "#FF4D6A"
WIN_CLOSE = "#E81123"
FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Inter", "sans-serif"]


@dataclass(frozen=True)
class Palette:
    mode: str
    window: str          # uygulama arka planı
    panel: str           # TitleBar, SidePanel, ControlBar
    surface: str         # kartlar
    hover: str
    active: str
    border: str
    border_strong: str
    text: str
    text2: str
    muted: str


DARK = Palette(
    "dark", window="#0A0C10", panel="#101319", surface="#171B23", hover="#1E232D",
    active="#272D39", border="#1C212B", border_strong="#2A303C",
    text="#E8EBF1", text2="#9BA3B4", muted="#5E6677",
)
LIGHT = Palette(
    "light", window="#EEF1F6", panel="#FFFFFF", surface="#F4F6FA", hover="#E8ECF3",
    active="#DCE2EC", border="#E2E6EE", border_strong="#C9D0DC",
    text="#121620", text2="#4F586B", muted="#5F687D",
)


def with_alpha(color: QColor | str, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def _rgba(color: QColor | str, alpha: int) -> str:
    c = QColor(color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{int(alpha)})"


def _luminance(c: QColor) -> float:
    def ch(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tipografi ve biçim yardımcıları
# ─────────────────────────────────────────────────────────────────────────────
def ui_font(px: int = 13, weight: QFont.Weight = QFont.Weight.Normal, tracking: float = 0.0) -> QFont:
    """tracking: yüzde cinsinden harf aralığı (başlıklarda -1…-2, küçük etiketlerde +0.5)."""
    f = QFont()
    f.setFamilies(FONT_FAMILIES)
    f.setPixelSize(px)
    f.setWeight(weight)
    if tracking:
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100.0 + tracking)
    return f


def mix(a: QColor | str, b: QColor | str, t: float) -> QColor:
    """a'dan b'ye t (0..1) oranında doğrusal renk karışımı."""
    ca, cb = QColor(a), QColor(b)
    return QColor(int(ca.red() + (cb.red() - ca.red()) * t), int(ca.green() + (cb.green() - ca.green()) * t),
                  int(ca.blue() + (cb.blue() - ca.blue()) * t), int(ca.alpha() + (cb.alpha() - ca.alpha()) * t))


def format_time(ms: int | float) -> str:
    """92_000 → '1:32', 3_725_000 → '1:02:05' (oynatıcı zaman etiketleri)."""
    total = max(0, int(ms // 1000))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_hms(seconds: int | float) -> str:
    """6135 → '01:42:15' (çalma listesi süre sütunu)."""
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Tema yöneticisi
# ─────────────────────────────────────────────────────────────────────────────
class ThemeManager(QObject):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._mode = "dark"
        self._accent_name = "Blue"
        self._accent = QColor(ACCENTS["Blue"])
        self._app: QApplication | None = None

    # -- okuma ----------------------------------------------------------------
    @property
    def p(self) -> Palette:
        return DARK if self._mode == "dark" else LIGHT

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def accent_name(self) -> str:
        return self._accent_name

    @property
    def accent(self) -> QColor:
        return QColor(self._accent)

    @property
    def accent_hover(self) -> QColor:
        return self._accent.lighter(115)

    @property
    def accent_pressed(self) -> QColor:
        return self._accent.darker(118)

    @property
    def accent_alt(self) -> QColor:
        """Logo/ikon gradyanı için vurgunun hafif kaydırılmış tonu."""
        h, s, v, _ = self._accent.getHsvF()
        h = 0.0 if h < 0 else h
        return QColor.fromHsvF((h + 0.09) % 1.0, min(1.0, s * 0.95), max(0.55, v * 0.88))

    @property
    def accent_text(self) -> QColor:
        """Metin olarak kullanılan vurgu: açık temada beyaz zemin üstünde ≥ 4.7:1 olana dek koyulaştırılır."""
        c = QColor(self._accent)
        if self._mode == "dark":
            return c
        for _ in range(24):
            if 1.05 / (_luminance(c) + 0.05) >= 4.7:
                break
            c = c.darker(105)
        return c

    @property
    def on_accent(self) -> QColor:
        """Vurgu üstündeki metin/ikon: yeterli kontrast için beyaz ya da koyu."""
        white_contrast = 1.05 / (_luminance(self._accent) + 0.05)
        return QColor("#FFFFFF") if white_contrast >= 3.0 else QColor("#0A0C10")

    def color(self, token: str, alpha: int | None = None) -> QColor:
        c = QColor(getattr(self.p, token))
        if alpha is not None:
            c.setAlpha(alpha)
        return c

    # -- değiştirme -----------------------------------------------------------
    def set_accent(self, value: str) -> None:
        if value in ACCENTS:
            self._accent_name, color = value, QColor(ACCENTS[value])
        else:
            color = QColor(value)
            if not color.isValid():
                raise ValueError(f"Geçersiz vurgu rengi: {value!r}")
            self._accent_name = color.name().upper()
        self._accent = color
        self._refresh()

    def set_mode(self, mode: str) -> None:
        if mode not in ("dark", "light"):
            raise ValueError("mode 'dark' veya 'light' olmalı")
        self._mode = mode
        self._refresh()

    def apply(self, app: QApplication | None = None) -> None:
        self._app = app or QApplication.instance()
        if self._app is not None:
            self._app.setFont(ui_font(13))
        self._refresh()

    def _refresh(self) -> None:
        if self._app is not None:
            self._app.setStyleSheet(self.stylesheet())
        self.changed.emit()

    # -- QSS ------------------------------------------------------------------
    def stylesheet(self) -> str:
        p, a = self.p, self._accent
        tokens = dict(
            window=p.window, panel=p.panel, surface=p.surface, hover=p.hover,
            active=p.active, border=p.border, border_strong=p.border_strong,
            text=p.text, text2=p.text2, muted=p.muted,
            accent=a.name(), accent_text=self.accent_text.name(), accent_hover=self.accent_hover.name(),
            accent_pressed=self.accent_pressed.name(),
            accent_soft=_rgba(a, 41), accent_softer=_rgba(a, 26),
            accent_line=_rgba(a, 90), accent_sel=_rgba(a, 70),
            on_accent=self.on_accent.name(),
            panel_hi=mix(p.panel, a, 0.07 if p.mode == 'dark' else 0.05).name(),
            window_hi=mix(p.window, a, 0.05 if p.mode == 'dark' else 0.04).name(),
            seg=_rgba(p.text, 13 if p.mode == 'dark' else 9),
            seg_line=_rgba(p.text, 20 if p.mode == 'dark' else 16),
            danger=DANGER, danger_soft=_rgba(DANGER, 38), win_close=WIN_CLOSE,
        )
        return Template(_QSS).safe_substitute(tokens)


_QSS = """
/* ===== Taban ===== */
QWidget { color: $text; selection-background-color: $accent_sel; selection-color: $text; outline: 0; }
QMainWindow, QDialog, QMessageBox, QInputDialog { background: $panel; }
QWidget#Root { background: $window; }
QLabel { background: transparent; }
QLabel[role="display"]   { color: $text; }
QLabel[role="title"]     { font-size: 16px; font-weight: 600; color: $text; }
QLabel[role="heading"]   { font-size: 13px; font-weight: 600; color: $text; }
QLabel[role="secondary"] { font-size: 13px; color: $text2; }
QLabel[role="caption"]   { font-size: 11px; color: $muted; }
QLabel#TimeLabel         { font-size: 12px; font-weight: 600; color: $text2; }
QLabel#TimeLabel[tone="strong"] { color: $text; }

/* ===== Başlık çubuğu / paneller ===== */
QFrame#TitleBar  { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 $panel_hi, stop:1 $panel); border: none; border-bottom: 1px solid $border; }
QFrame#SidePanel { background: qlineargradient(x1:0,y1:0,x2:0,y2:0.42, stop:0 $panel_hi, stop:1 $panel); border: none; border-left: 1px solid $border; }
QFrame#SegGroup  { background: $seg; border: 1px solid $seg_line; border-radius: 12px; }
QFrame#QuickGroup { background: $seg; border: 1px solid $seg_line; border-radius: 15px; }
QWidget#VideoSurface { background: #000000; }
QWidget#PlaylistContent { background: transparent; }
QFrame[role="divider"] { background: $border; border: none; max-height: 1px; min-height: 1px; }

/* ===== Rozetler / bilgi kartları ===== */
QLabel#CountBadge {
    background: $accent_soft; color: $accent_text; border-radius: 10px; border: 1px solid $accent_line;
    padding: 2px 9px; font-size: 11px; font-weight: 600;
}
QFrame#FolderBanner { background: $accent_softer; border: 1px solid $accent_line; border-radius: 10px; }
QFrame#FolderBanner QLabel { color: $text; font-size: 12px; font-weight: 600; }
QFrame#IconTile { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 $accent_soft, stop:1 $surface); border: 1px solid $accent_line; border-radius: 24px; }
QLabel#TimeBubble {
    background: $surface; color: $text; border: 1px solid $border_strong;
    border-radius: 8px; padding: 3px 9px; font-size: 12px; font-weight: 600;
}

/* ===== Düğmeler (QPushButton) ===== */
QPushButton {
    background: $surface; border: 1px solid $border; border-radius: 10px;
    padding: 8px 16px; color: $text; font-weight: 500;
}
QPushButton:hover    { background: $hover; border-color: $border_strong; }
QPushButton:pressed  { background: $active; }
QPushButton:disabled { color: $muted; background: $panel; }
QPushButton[variant="primary"] { background: $accent; border: 1px solid $accent; color: $on_accent; font-weight: 600; }
QPushButton[variant="primary"]:hover   { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:pressed { background: $accent_pressed; }
QPushButton[variant="ghost"] { background: transparent; border: 1px solid transparent; color: $text2; }
QPushButton[variant="ghost"]:hover { background: $hover; color: $text; }
QPushButton[variant="danger"] { background: transparent; border: 1px solid transparent; color: $text2; }
QPushButton[variant="danger"]:hover { background: $danger_soft; color: $danger; }

/* ===== Giriş alanları ===== */
QLineEdit {
    background: $surface; border: 1px solid $border; border-radius: 8px;
    padding: 7px 10px; color: $text;
}
QLineEdit:hover { border-color: $border_strong; }
QLineEdit:focus { border: 1px solid $accent; }
QLineEdit#SearchBox { border-radius: 12px; padding: 9px 8px 9px 2px; background: $seg; border: 1px solid $seg_line; }
QLineEdit#SearchBox:focus { background: $surface; border: 1px solid $accent; }

/* ===== Liste / kaydırma çubukları ===== */
QListView#PlaylistList { background: transparent; border: none; }
QAbstractScrollArea { background: transparent; border: none; }
QScrollBar:vertical   { background: transparent; width: 8px;  margin: 2px 2px 2px 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0 2px 2px 2px; }
QScrollBar::handle:vertical   { background: $border_strong; border-radius: 2px; min-height: 36px; margin: 0 1px; }
QScrollBar::handle:horizontal { background: $border_strong; border-radius: 3px; min-width: 36px; margin: 2px 0; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: $muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; background: none; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

/* ===== Menüler / ipuçları ===== */
QMenu { background: $panel; border: 1px solid $border_strong; border-radius: 12px; padding: 6px; }
QMenu::item { padding: 8px 26px 8px 8px; border-radius: 8px; margin: 1px 0; color: $text; }
QMenu::item:selected { background: $hover; }
QMenu::item:disabled { color: $muted; }
QMenu::icon { padding-left: 6px; }
QMenu::separator { height: 1px; background: $border; margin: 5px 6px; }
QToolTip { background: $surface; color: $text; border: 1px solid $border_strong; padding: 5px 8px; }
"""

theme = ThemeManager()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Vektörel ikon seti (24×24 ızgara)
# ─────────────────────────────────────────────────────────────────────────────
_ICONS: dict[str, Callable[[QPainter, QColor], None]] = {}


def _icon(*names: str):
    def deco(fn):
        for n in names:
            _ICONS[n] = fn
        return fn
    return deco


def _stroke(p: QPainter, c: QColor, w: float = 1.8) -> None:
    p.setPen(QPen(c, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _fill(p: QPainter, c: QColor, edge: float = 1.4) -> None:
    p.setPen(QPen(c, edge, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(c)


def _pts(*pts: tuple[float, float]) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in pts])


@_icon("play")
def _i_play(p, c):
    _fill(p, c); p.drawPolygon(_pts((8.5, 5.2), (19, 12), (8.5, 18.8)))


@_icon("pause")
def _i_pause(p, c):
    _fill(p, c, 1.0)
    p.drawRoundedRect(QRectF(6.5, 5, 3.8, 14), 1.4, 1.4)
    p.drawRoundedRect(QRectF(13.7, 5, 3.8, 14), 1.4, 1.4)


@_icon("stop")
def _i_stop(p, c):
    _fill(p, c, 1.0); p.drawRoundedRect(QRectF(6, 6, 12, 12), 2.2, 2.2)


@_icon("prev")
def _i_prev(p, c):
    _fill(p, c, 1.2)
    p.drawRoundedRect(QRectF(5.2, 5.5, 2.4, 13), 1.1, 1.1)
    p.drawPolygon(_pts((19, 5.6), (9.6, 12), (19, 18.4)))


@_icon("next")
def _i_next(p, c):
    _fill(p, c, 1.2)
    p.drawRoundedRect(QRectF(16.4, 5.5, 2.4, 13), 1.1, 1.1)
    p.drawPolygon(_pts((5, 5.6), (14.4, 12), (5, 18.4)))


def _skip(p: QPainter, c: QColor, forward: bool) -> None:
    p.save()
    if not forward:
        p.translate(24, 0); p.scale(-1, 1)
    _stroke(p, c, 1.7)
    path = QPainterPath()
    rect = QRectF(4.5, 5.5, 15, 15)
    path.arcMoveTo(rect, 90)
    path.arcTo(rect, 90, 300)
    p.drawPath(path)
    p.drawPolyline(_pts((10.4, 3.2), (13, 5.5), (10.4, 7.8)))
    p.restore()
    f = ui_font(7, QFont.Weight.Bold)
    f.setPixelSize(7)
    p.setFont(f); p.setPen(c)
    p.drawText(QRectF(4.5, 6.2, 15, 15), Qt.AlignmentFlag.AlignCenter, "10")


@_icon("back10")
def _i_back10(p, c): _skip(p, c, False)


@_icon("fwd10")
def _i_fwd10(p, c): _skip(p, c, True)


def _speaker(p: QPainter, c: QColor) -> None:
    _fill(p, c, 1.2)
    p.drawPolygon(_pts((4, 9.6), (7.8, 9.6), (12.4, 5.6), (12.4, 18.4), (7.8, 14.4), (4, 14.4)))
    _stroke(p, c, 1.7)


@_icon("volume_mute")
def _i_vmute(p, c):
    _speaker(p, c)
    p.drawLine(QPointF(16.2, 9.6), QPointF(21, 14.4))
    p.drawLine(QPointF(21, 9.6), QPointF(16.2, 14.4))


@_icon("volume_low")
def _i_vlow(p, c):
    _speaker(p, c)
    p.drawArc(QRectF(8.4, 8, 8, 8), -45 * 16, 90 * 16)


@_icon("volume_high")
def _i_vhigh(p, c):
    _speaker(p, c)
    p.drawArc(QRectF(8.4, 8, 8, 8), -45 * 16, 90 * 16)
    p.drawArc(QRectF(5.4, 4.6, 14.8, 14.8), -48 * 16, 96 * 16)


@_icon("subtitles")
def _i_subs(p, c):
    _stroke(p, c, 1.7)
    p.drawRoundedRect(QRectF(3.4, 5.6, 17.2, 12.8), 3.2, 3.2)
    p.drawLine(QPointF(6.8, 10.6), QPointF(10.2, 10.6)); p.drawLine(QPointF(12.4, 10.6), QPointF(17.2, 10.6))
    p.drawLine(QPointF(6.8, 14), QPointF(12.8, 14)); p.drawLine(QPointF(15, 14), QPointF(17.2, 14))


@_icon("audio_track")
def _i_audio(p, c):
    _stroke(p, c, 2.0)
    for x, h in ((5, 3), (8.5, 7), (12, 10), (15.5, 6), (19, 3)):
        p.drawLine(QPointF(x, 12 - h / 2), QPointF(x, 12 + h / 2))


@_icon("camera")
def _i_camera(p, c):
    _stroke(p, c, 1.7)
    path = QPainterPath()
    path.moveTo(3.6, 9.6); path.quadTo(3.6, 8, 5.2, 8); path.lineTo(8.4, 8)
    path.lineTo(9.8, 5.8); path.lineTo(14.2, 5.8); path.lineTo(15.6, 8); path.lineTo(18.8, 8)
    path.quadTo(20.4, 8, 20.4, 9.6); path.lineTo(20.4, 17.2); path.quadTo(20.4, 18.8, 18.8, 18.8)
    path.lineTo(5.2, 18.8); path.quadTo(3.6, 18.8, 3.6, 17.2); path.closeSubpath()
    p.drawPath(path)
    p.drawEllipse(QPointF(12, 13.2), 3.3, 3.3)


@_icon("pip")
def _i_pip(p, c):
    _stroke(p, c, 1.7)
    p.drawRoundedRect(QRectF(3.4, 5.4, 17.2, 13.2), 3, 3)
    _fill(p, c, 1.0)
    p.drawRoundedRect(QRectF(11.6, 11.6, 6.4, 4.4), 1.3, 1.3)


@_icon("playlist")
def _i_playlist(p, c):
    _stroke(p, c, 1.8)
    for y, x2 in ((7, 14.5), (12, 14.5), (17, 10.5)):
        p.drawLine(QPointF(4, y), QPointF(x2, y))
    _fill(p, c, 1.2)
    p.drawPolygon(_pts((16.6, 11), (21, 14.4), (16.6, 17.8)))


@_icon("fullscreen")
def _i_full(p, c):
    _stroke(p, c, 1.8)
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        cx, cy = (4.2 if sx > 0 else 19.8), (4.2 if sy > 0 else 19.8)
        p.drawPolyline(_pts((cx, cy + 5 * sy), (cx, cy), (cx + 5 * sx, cy)))


@_icon("fullscreen_exit")
def _i_fullx(p, c):
    _stroke(p, c, 1.8)
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        cx, cy = (9.4 if sx > 0 else 14.6), (9.4 if sy > 0 else 14.6)
        p.drawPolyline(_pts((cx - 5 * sx, cy), (cx, cy), (cx, cy - 5 * sy)))


@_icon("win_min")
def _i_wmin(p, c):
    _stroke(p, c, 1.2); p.drawLine(QPointF(7, 12.5), QPointF(17, 12.5))


@_icon("win_max")
def _i_wmax(p, c):
    _stroke(p, c, 1.2); p.drawRoundedRect(QRectF(7.2, 7.2, 9.6, 9.6), 1.4, 1.4)


@_icon("win_restore")
def _i_wrest(p, c):
    _stroke(p, c, 1.2)
    p.drawRoundedRect(QRectF(6.8, 9.4, 8, 8), 1.4, 1.4)
    p.drawPolyline(_pts((9.4, 9.4), (9.4, 7.4), (17, 7.4), (17, 15), (14.8, 15)))


@_icon("win_close", "close")
def _i_close(p, c):
    _stroke(p, c, 1.5)
    p.drawLine(QPointF(7, 7), QPointF(17, 17)); p.drawLine(QPointF(17, 7), QPointF(7, 17))


@_icon("folder")
def _i_folder(p, c):
    _stroke(p, c, 1.7)
    path = QPainterPath()
    path.moveTo(3.6, 8); path.quadTo(3.6, 6.4, 5.2, 6.4); path.lineTo(9, 6.4); path.lineTo(11, 8.6)
    path.lineTo(18.8, 8.6); path.quadTo(20.4, 8.6, 20.4, 10.2); path.lineTo(20.4, 17.4)
    path.quadTo(20.4, 19, 18.8, 19); path.lineTo(5.2, 19); path.quadTo(3.6, 19, 3.6, 17.4); path.closeSubpath()
    p.drawPath(path)


@_icon("file")
def _i_file(p, c):
    _stroke(p, c, 1.7)
    path = QPainterPath()
    path.moveTo(6.4, 3.8); path.lineTo(13.6, 3.8); path.lineTo(18.4, 8.6); path.lineTo(18.4, 19.2)
    path.quadTo(18.4, 20.4, 17.2, 20.4); path.lineTo(6.4, 20.4)
    path.quadTo(5.2, 20.4, 5.2, 19.2); path.lineTo(5.2, 5); path.quadTo(5.2, 3.8, 6.4, 3.8)
    p.drawPath(path)
    p.drawPolyline(_pts((13.4, 3.9), (13.4, 8.8), (18.3, 8.8)))


@_icon("link")
def _i_link(p, c):
    _stroke(p, c, 1.7)
    p.save(); p.translate(12, 12); p.rotate(-45)
    p.drawRoundedRect(QRectF(-9.4, -3, 10.6, 6), 3, 3)
    p.drawRoundedRect(QRectF(-1.2, -3, 10.6, 6), 3, 3)
    p.restore()


@_icon("settings")
def _i_settings(p, c):
    _stroke(p, c, 1.7)
    p.drawEllipse(QPointF(12, 12), 5.0, 5.0)
    p.drawEllipse(QPointF(12, 12), 1.9, 1.9)
    for i in range(8):
        a = math.radians(i * 45)
        p.drawLine(QPointF(12 + 6.6 * math.cos(a), 12 + 6.6 * math.sin(a)),
                   QPointF(12 + 9 * math.cos(a), 12 + 9 * math.sin(a)))


@_icon("search")
def _i_search(p, c):
    _stroke(p, c, 1.8)
    p.drawEllipse(QPointF(10.6, 10.6), 5.6, 5.6)
    p.drawLine(QPointF(14.8, 14.8), QPointF(19.6, 19.6))


@_icon("shuffle")
def _i_shuffle(p, c):
    _stroke(p, c, 1.7)
    p.drawPolyline(_pts((3.6, 7.6), (8.2, 7.6), (14.8, 16.4), (18, 16.4)))
    p.drawPolyline(_pts((3.6, 16.4), (8.2, 16.4), (14.8, 7.6), (18, 7.6)))
    _fill(p, c, 1.0)
    p.drawPolygon(_pts((17.4, 5), (21.2, 7.6), (17.4, 10.2)))
    p.drawPolygon(_pts((17.4, 13.8), (21.2, 16.4), (17.4, 19)))


@_icon("repeat")
def _i_repeat(p, c):
    _stroke(p, c, 1.7)
    top = QPainterPath(); top.moveTo(4.6, 12.4); top.lineTo(4.6, 10.2); top.quadTo(4.6, 7.6, 7.2, 7.6); top.lineTo(17, 7.6)
    bot = QPainterPath(); bot.moveTo(19.4, 11.6); bot.lineTo(19.4, 13.8); bot.quadTo(19.4, 16.4, 16.8, 16.4); bot.lineTo(7, 16.4)
    p.drawPath(top); p.drawPath(bot)
    _fill(p, c, 1.0)
    p.drawPolygon(_pts((16.2, 4.8), (20.4, 7.6), (16.2, 10.4)))
    p.drawPolygon(_pts((7.8, 13.6), (3.6, 16.4), (7.8, 19.2)))


@_icon("sequential")
def _i_seq(p, c):
    _stroke(p, c, 1.8)
    p.drawLine(QPointF(4.4, 12), QPointF(19, 12))
    p.drawPolyline(_pts((14.2, 7.2), (19, 12), (14.2, 16.8)))


@_icon("sort")
def _i_sort(p, c):
    _stroke(p, c, 1.8)
    for y, x2 in ((7, 13.5), (12, 11.5), (17, 9.5)):
        p.drawLine(QPointF(4, y), QPointF(x2, y))
    p.drawLine(QPointF(18, 6), QPointF(18, 18))
    p.drawPolyline(_pts((15.4, 15.4), (18, 18), (20.6, 15.4)))


@_icon("export")
def _i_export(p, c):
    _stroke(p, c, 1.8)
    p.drawLine(QPointF(12, 4), QPointF(12, 14.4))
    p.drawPolyline(_pts((8.2, 10.8), (12, 14.6), (15.8, 10.8)))
    p.drawPolyline(_pts((5, 15.4), (5, 19.4), (19, 19.4), (19, 15.4)))


_ICONS["download"] = _i_export


@_icon("trash")
def _i_trash(p, c):
    _stroke(p, c, 1.7)
    p.drawLine(QPointF(4.8, 7), QPointF(19.2, 7))
    p.drawPolyline(_pts((9.4, 7), (9.4, 4.8), (14.6, 4.8), (14.6, 7)))
    p.drawPolyline(_pts((6.6, 7), (7.6, 19.4), (16.4, 19.4), (17.4, 7)))
    p.drawLine(QPointF(10.4, 10.4), QPointF(10.4, 16)); p.drawLine(QPointF(13.6, 10.4), QPointF(13.6, 16))


@_icon("music")
def _i_music(p, c):
    _stroke(p, c, 1.8)
    p.drawLine(QPointF(15.6, 4.6), QPointF(15.6, 16.2))
    p.drawPolyline(_pts((15.6, 4.6), (19.6, 6.4), (19.6, 9.4)))
    _fill(p, c, 1.0)
    p.drawEllipse(QPointF(11.8, 17.2), 3.6, 2.9)


@_icon("video")
def _i_video(p, c):
    _stroke(p, c, 1.7)
    p.drawRoundedRect(QRectF(3.4, 5, 17.2, 14), 3.4, 3.4)
    _fill(p, c, 1.2)
    p.drawPolygon(_pts((10.2, 9.2), (15, 12), (10.2, 14.8)))


@_icon("check")
def _i_check(p, c):
    _stroke(p, c, 2.0)
    p.drawPolyline(_pts((5.4, 12.6), (10, 17), (18.6, 7.4)))


@_icon("blank")
def _i_blank(p, c):
    return


@lru_cache(maxsize=4096)
def _render_icon(name: str, rgba: int, size: int, dpr: float) -> QPixmap:
    px = max(1, int(round(size * dpr)))
    pm = QPixmap(px, px)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    p.scale(size / 24.0, size / 24.0)
    _ICONS[name](p, QColor.fromRgba(rgba))
    p.end()
    return pm


def icon_pixmap(name: str, color: QColor | str | None = None, size: int = 20, dpr: float = 2.0) -> QPixmap:
    """Vektör ikonu verilen renk ve boyutta (varsayılan 2× keskin) QPixmap olarak döndürür."""
    c = QColor(color) if color is not None else QColor(theme.p.text2)
    return _render_icon(name, c.rgba(), int(size), float(dpr))


def icon(name: str, color: QColor | str | None = None, size: int = 20) -> QIcon:
    return QIcon(icon_pixmap(name, color, size))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Logo
# ─────────────────────────────────────────────────────────────────────────────
def paint_logo(p: QPainter, rect: QRectF, accent: QColor | None = None) -> None:
    """Lumina simgesi: yumuşak renk geçişli yuvarlak kare + oynat üçgeni."""
    accent = accent or theme.accent
    s = min(rect.width(), rect.height())
    r = QRectF(rect.center().x() - s / 2, rect.center().y() - s / 2, s, s)
    h, sat, v, _ = accent.getHsvF()
    h = 0.0 if h < 0 else h
    c_a = QColor(accent).lighter(122)
    c_b = QColor.fromHsvF((h + 0.09) % 1.0, min(1.0, sat * 0.95), max(0.55, v * 0.86))
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath(); path.addRoundedRect(r, s * 0.30, s * 0.30)
    g = QLinearGradient(r.topLeft(), r.bottomRight()); g.setColorAt(0, c_a); g.setColorAt(1, c_b)
    p.fillPath(path, g)
    hl = QRadialGradient(QPointF(r.left() + s * 0.28, r.top() + s * 0.2), s * 0.7)
    hl.setColorAt(0, QColor(255, 255, 255, 80)); hl.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(path, hl)
    p.setPen(QPen(QColor(255, 255, 255, 46), max(1.0, s / 64))); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    tri = QPolygonF([QPointF(r.left() + s * 0.39, r.top() + s * 0.29),
                     QPointF(r.left() + s * 0.74, r.top() + s * 0.50),
                     QPointF(r.left() + s * 0.39, r.top() + s * 0.71)])
    p.setPen(QPen(QColor("#FFFFFF"), s * 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(QColor("#FFFFFF")); p.drawPolygon(tri)
    p.restore()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Paylaşılan bileşenler
# ─────────────────────────────────────────────────────────────────────────────
def make_menu(parent: QWidget | None = None) -> QMenu:
    """Yuvarlak köşeli, gölgesiz, QSS ile biçimlenen menü."""
    m = QMenu(parent)
    m.setWindowFlags(m.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
    m.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    return m


def populate_choice_menu(menu: QMenu, entries: Sequence[tuple[str, object]], current: object,
                         on_select: Callable[[object], None]) -> None:
    """Tek seçimli menü: seçili öğe vurgu renkli onay ikonuyla işaretlenir."""
    menu.clear()
    blank = icon("blank", size=16)
    tick = icon("check", theme.accent, 16)
    for label, value in entries:
        act = QAction(label, menu)
        act.setIcon(tick if value == current else blank)
        act.triggered.connect(lambda _=False, v=value: on_select(v))
        menu.addAction(act)


class ElidedLabel(QLabel):
    """Genişliğe göre sonu '…' ile kısaltılan etiket (QSS ile uyumlu)."""

    def __init__(self, text: str = "", parent: QWidget | None = None,
                 mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight) -> None:
        super().__init__(parent)
        self._full = text
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._apply()

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text
        self._apply()

    def fullText(self) -> str:  # noqa: N802
        return self._full

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, super().minimumSizeHint().height())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.fontMetrics().horizontalAdvance(self._full) + 2, super().sizeHint().height())

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._apply()

    def _apply(self) -> None:
        w = max(0, self.contentsRect().width())
        el = self.fontMetrics().elidedText(self._full, self._mode, w) if w else self._full
        QLabel.setText(self, el)
        self.setToolTip(self._full if el != self._full else "")


class IconButton(QToolButton):
    """Tamamen özel çizilen (QPainter) düz ikon/metin düğmesi.

    variant: "default" | "titlebar" | "close" | "danger"
    Hover/pressed/checked durumlarını ve vurgu rengini temadan okur.
    """

    def __init__(self, icon_name: str = "", tooltip: str = "", size: int | tuple[int, int] = 36,
                 icon_size: int = 20, *, checkable: bool = False, round_: bool = False,
                 variant: str = "default", text: str = "", radius: int = 10,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = radius
        self._name = icon_name
        self._icon_size = icon_size
        self._round = round_
        self._variant = variant
        self._label = text
        self._show_text = True
        self._menu: QMenu | None = None
        self._menu_up = False
        self._hover = False
        w, h = (size, size) if isinstance(size, int) else size
        self._w, self._h = w, h
        self.setFixedSize(w, h)
        self.setCheckable(checkable)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        theme.changed.connect(self.update)

    def set_icon_name(self, name: str) -> None:
        if name != self._name:
            self._name = name
            self.update()

    def set_label(self, text: str) -> None:
        self._label = text
        self.update()

    def set_show_text(self, show: bool, collapsed_width: int | None = None) -> None:
        self._show_text = show
        self.setFixedWidth(self._w if show or collapsed_width is None else collapsed_width)
        self.update()

    def attach_menu(self, menu: QMenu, up: bool = False) -> None:
        self._menu, self._menu_up = menu, up
        self.clicked.connect(self._popup)

    def _popup(self) -> None:
        m = self._menu
        if m is None:
            return
        m.ensurePolished()
        sh = m.sizeHint()
        if self._menu_up:
            pos = self.mapToGlobal(QPoint(self.width() // 2 - sh.width() // 2, -sh.height() - 8))
        else:
            pos = self.mapToGlobal(QPoint(self.width() - sh.width(), self.height() + 6))
        m.exec(pos)
        self._hover = self.underMouse()
        self.update()

    def enterEvent(self, e) -> None:  # noqa: N802
        self._hover = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, _e) -> None:  # noqa: N802
        pal, acc = theme.p, theme.accent
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        enabled, down, checked = self.isEnabled(), self.isDown(), self.isChecked()
        hover = self._hover and enabled
        bg: QColor | None = None
        fg = QColor(pal.text2)
        if self._variant == "close":
            if hover:
                bg, fg = QColor(WIN_CLOSE), QColor("#FFFFFF")
                if down:
                    bg = QColor("#F1707A")
        elif self._variant == "danger":
            if hover:
                bg, fg = with_alpha(DANGER, 38), QColor(DANGER)
        elif self._variant == "pill":
            bg = with_alpha(pal.text, 26 if hover else 14); fg = QColor(pal.text if hover else pal.text2)
        elif checked:
            bg, fg = with_alpha(acc, 62 if hover else 41), acc
        elif hover:
            bg, fg = QColor(pal.active if down else pal.hover), QColor(pal.text)
        if not enabled:
            fg = with_alpha(pal.muted, 150)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 0 if self._variant in ("titlebar", "close") else (
            min(rect.width(), rect.height()) / 2 if (self._round or self._variant == "pill") else self._radius)
        if bg is not None:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(bg)
            p.drawRoundedRect(rect, radius, radius)
        if self._variant == "pill":
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(with_alpha(pal.text, 30), 1))
            p.drawRoundedRect(rect, radius, radius)
        text = self._label if self._show_text else ""
        font = ui_font(12, QFont.Weight.DemiBold)
        p.setFont(font)
        tw = p.fontMetrics().horizontalAdvance(text) if text else 0
        iw = self._icon_size if self._name else 0
        gap = 8 if (iw and tw) else 0
        x = (self.width() - (iw + gap + tw)) / 2
        if iw:
            pm = icon_pixmap(self._name, fg, self._icon_size)
            p.drawPixmap(QPointF(x, (self.height() - iw) / 2), pm)
            x += iw + gap
        if text:
            p.setPen(fg)
            p.drawText(QRectF(x, 0, tw + 2, self.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# 7. Derinlik araçları: gölge, cam yüzey, aurora, kapak karosu
# ─────────────────────────────────────────────────────────────────────────────
def soft_shadow(p: QPainter, rect: QRectF, radius: float, *, layers: int = 7, dy: float = 8.0,
                alpha: int = 26, spread: float = 1.7, color: QColor | None = None) -> None:
    """Çok katmanlı, bantlaşmayan yumuşak gölge. `alpha` ≈ çekirdekteki yoğunluğun beşte biri."""
    n = max(8, layers * 2)
    per = max(1, int(alpha * 2.4 / n + 0.5))
    base = QColor(color) if color is not None else QColor(0, 0, 0)
    base.setAlpha(per)
    p.save(); p.setPen(Qt.PenStyle.NoPen); p.setBrush(base)
    for i in range(n, 0, -1):
        k = i / n
        g = k * layers * spread
        p.drawRoundedRect(rect.adjusted(-g, -g * 0.35 + dy * k * 0.45, g, g + dy * k), radius + g, radius + g)
    p.restore()


def paint_glass(p: QPainter, rect: QRectF, radius: float, *, alpha: int = 238, tint: QColor | None = None) -> None:
    """Cam yüzey: üstte hafif aydınlık dikey gradyan + üstten sönen 1 px ışık çizgisi."""
    pal = theme.p
    dark = theme.mode == "dark"
    base = QColor(pal.panel if tint is None else tint)
    top = mix(base, "#FFFFFF", 0.075 if dark else 0.0)
    top.setAlpha(alpha); base.setAlpha(alpha)
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft()); g.setColorAt(0, top); g.setColorAt(1, base)
    p.save(); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(g); p.drawRoundedRect(rect, radius, radius)
    edge = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    edge.setColorAt(0, with_alpha("#FFFFFF", 70 if dark else 230))
    edge.setColorAt(0.45, with_alpha(pal.border_strong, 200))
    edge.setColorAt(1, with_alpha(pal.border_strong, 120))
    p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QBrush(edge), 1))
    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    p.restore()


def paint_aurora(p: QPainter, rect: QRectF, intensity: float = 1.0) -> None:
    """Vurgu renginden türeyen, çok yumuşak ortam ışığı (ışık kaynağı: logo/kapak)."""
    a, b = theme.accent, theme.accent_alt
    k = intensity * (1.0 if theme.mode == "dark" else 0.75)
    W, H = rect.width(), rect.height()
    p.save()
    for fx, fy, fr, c, al in ((0.50, 0.24, 0.46, a, 62), (0.84, 0.40, 0.40, b, 38), (0.12, 0.85, 0.42, b, 20), (0.50, 1.05, 0.7, a, 16)):
        r = max(W, H) * fr
        g = QRadialGradient(QPointF(rect.left() + W * fx, rect.top() + H * fy), r)
        g.setColorAt(0, with_alpha(c, int(al * k))); g.setColorAt(1, with_alpha(c, 0))
        p.fillRect(rect, QBrush(g))
    p.restore()


def tile_colors(seed: str) -> tuple[QColor, QColor]:
    """Başlıktan türetilen, vurgu tonuna yakın (±40°) uyumlu kapak karosu gradyanı."""
    h0, _, _, _ = theme.accent.getHsvF()
    h0 = 0.6 if h0 < 0 else h0
    k = (zlib.crc32(seed.encode("utf-8")) % 1000) / 1000.0
    hue = (h0 + (k - 0.5) * 0.16) % 1.0
    dark = theme.mode == "dark"
    c1 = QColor.fromHsvF(hue, 0.58 if dark else 0.50, 0.95)
    c2 = QColor.fromHsvF((hue + 0.05) % 1.0, 0.82, 0.58 if dark else 0.72)
    # üstündeki beyaz sıra numarası/ikon okunsun: orta ton ≥ 3:1 olana dek ikisini birlikte koyulaştır
    for _ in range(14):
        if 1.05 / (_luminance(mix(c1, c2, 0.5)) + 0.05) >= 3.0:
            break
        c1, c2 = c1.darker(108), c2.darker(108)
    return c1, c2


# ── Geriye dönük uyumluluk yardımcıları ──────────────────────────────────────────
def palette() -> Palette:
    return theme.p

def build_stylesheet(mode: str | None = None, accent: str | None = None) -> str:
    if mode:
        theme.set_mode('dark' if mode != 'light' else 'light')
    if accent:
        theme.set_accent(accent)
    return theme.stylesheet()

def apply_theme(mode: str = 'dark', accent: str = 'blue') -> Palette:
    theme.set_mode('dark' if mode != 'light' else 'light')
    theme.set_accent(accent)
    return theme.p
