"""
Lumina Player — control_bar.py
==============================
Video üzerinde yüzen, yarı saydam kontrol çubuğu.

* SeekBar / VolumeSlider : özel çizimli ModernSlider (hover balonu, tamponlu bölge)
* PlayButton             : 40×40 yuvarlak vurgulu oynat/duraklat
* ControlBar             : iki satırlı yüzen çubuk, 3 sn hareketsizlikte yumuşakça gizlenir

Entegrasyon::

    bar = ControlBar(); bar.attach_to(video_container)   # alt ortaya yerleşir, otomatik gizlenir
    bar.playPauseClicked.connect(player.toggle)
    bar.seekRequested.connect(player.set_position)        # ms
    player.positionChanged.connect(bar.set_position)
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEvent, QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QSizePolicy, QVBoxLayout, QWidget,
)

from lumina.ui.theme import (
    IconButton, format_time, icon_pixmap, make_menu, mix, paint_glass, populate_choice_menu, soft_shadow, theme,
    ui_font, with_alpha,
)

SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0]


def _speed_text(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".") + "x" if v not in (1.0, 2.0, 3.0) else f"{v:.1f}x"


# ─────────────────────────────────────────────────────────────────────────────
class ModernSlider(QWidget):
    """Yatay, özel çizimli kaydırıcı. Fare üstünde iz kalınlaşır, tutamaç belirir."""

    valueChanged = Signal(int)          # her değişiklikte (kod veya kullanıcı)
    userValueChanged = Signal(int)      # yalnızca kullanıcı etkileşiminde
    userReleased = Signal(int)
    hoverValue = Signal(int)            # fare üstündeki konumun değeri (-1: dışarı çıktı)

    def __init__(self, minimum: int = 0, maximum: int = 1000, value: int = 0, *,
                 formatter=None, bubble: bool = True, marker: int | None = None,
                 warn_above: int | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._min, self._max, self._value = minimum, maximum, value
        self._buffered = 0
        self._formatter = formatter or (lambda v: str(v))
        self._marker = marker
        self._warn_above = warn_above
        self._dimmed = False
        self._hover = False
        self._hover_x = -1.0
        self._drag = False
        self.setMouseTracking(True)
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bubble: QLabel | None = None
        if bubble:
            b = QLabel()
            b.setObjectName("TimeBubble")
            b.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
                             | Qt.WindowType.WindowDoesNotAcceptFocus)
            b.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            b.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._bubble = b
        theme.changed.connect(self.update)

    # -- API ------------------------------------------------------------------
    def value(self) -> int: return self._value
    def maximum(self) -> int: return self._max
    def isDragging(self) -> bool: return self._drag  # noqa: N802

    def setRange(self, lo: int, hi: int) -> None:  # noqa: N802
        self._min, self._max = lo, max(lo + 1, hi)
        self.setValue(self._value)

    def setValue(self, v: int) -> None:  # noqa: N802
        v = max(self._min, min(self._max, int(v)))
        if v != self._value:
            self._value = v
            self.valueChanged.emit(v)
            self.update()

    def set_buffered(self, v: int) -> None:
        self._buffered = max(self._min, min(self._max, int(v))); self.update()

    def set_dimmed(self, on: bool) -> None:
        self._dimmed = on; self.update()

    # -- geometri -------------------------------------------------------------
    def _track(self) -> QRectF:
        pad = 6.0
        return QRectF(pad, 0, max(1.0, self.width() - 2 * pad), self.height())

    def _frac(self) -> float:
        return (self._value - self._min) / max(1, self._max - self._min)

    def _value_at(self, x: float) -> int:
        t = self._track()
        f = max(0.0, min(1.0, (x - t.left()) / t.width()))
        return int(round(self._min + f * (self._max - self._min)))

    # -- fare -----------------------------------------------------------------
    def enterEvent(self, e) -> None:  # noqa: N802
        self._hover = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = False; self._hover_x = -1
        if not self._drag:
            self._hide_bubble(); self.hoverValue.emit(-1)
        self.update(); super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._drag = True
            self._apply_pos(e.position().x(), e.globalPosition().toPoint())

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        self._hover_x = e.position().x()
        if self._drag:
            self._apply_pos(e.position().x(), e.globalPosition().toPoint())
        else:
            self._show_bubble(self._value_at(self._hover_x), e.globalPosition().toPoint())
            self.hoverValue.emit(self._value_at(self._hover_x))
            self.update()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if self._drag and e.button() == Qt.MouseButton.LeftButton:
            self._drag = False
            self.userReleased.emit(self._value)
            if not self.underMouse():
                self._hide_bubble()
            self.update()

    def wheelEvent(self, e) -> None:  # noqa: N802
        step = max(1, (self._max - self._min) // 40)
        delta = 1 if e.angleDelta().y() > 0 else -1
        self.setValue(self._value + delta * step)
        self.userValueChanged.emit(self._value)
        e.accept()

    def hideEvent(self, e) -> None:  # noqa: N802
        self._hide_bubble(); super().hideEvent(e)

    def _apply_pos(self, x: float, global_pos: QPoint) -> None:
        v = self._value_at(x)
        self._show_bubble(v, global_pos)
        if v != self._value:
            self._value = v
            self.valueChanged.emit(v)
        self.userValueChanged.emit(v)
        self.update()

    def _show_bubble(self, value: int, global_pos: QPoint) -> None:
        b = self._bubble
        if b is None:
            return
        b.setText(self._formatter(value))
        b.adjustSize()
        top = self.mapToGlobal(QPoint(0, 0)).y()
        b.move(global_pos.x() - b.width() // 2, top - b.height() - 6)
        if not b.isVisible():
            b.show()

    def _hide_bubble(self) -> None:
        if self._bubble is not None:
            try:
                self._bubble.hide()
            except RuntimeError:      # uygulama kapanırken Qt nesnesi silinmiş olabilir
                self._bubble = None

    # -- çizim ----------------------------------------------------------------
    def paintEvent(self, _e) -> None:  # noqa: N802
        pal, acc = theme.p, theme.accent
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._track()
        active = self._hover or self._drag
        h = 4.5 if active else 3.0
        cy = self.height() / 2
        track = QRectF(t.left(), cy - h / 2, t.width(), h)
        fill_color = acc
        if self._warn_above is not None and self._value > self._warn_above:
            fill_color = QColor("#FF8A3D")
        if self._dimmed or not self.isEnabled():
            fill_color = QColor(pal.muted)
        base = with_alpha(pal.text, 38 if theme.mode == "dark" else 46)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base); p.drawRoundedRect(track, h / 2, h / 2)
        if self._buffered > self._min:
            bf = (self._buffered - self._min) / max(1, self._max - self._min)
            p.setBrush(with_alpha(pal.text, 52))
            p.drawRoundedRect(QRectF(track.left(), track.top(), track.width() * bf, h), h / 2, h / 2)
        fw = track.width() * self._frac()
        if fw > 0:
            if self._dimmed or not self.isEnabled() or fill_color != acc:
                p.setBrush(fill_color)
            else:   # ışık izi: vurgudan kaydırılmış tona doğru akar
                lg = QLinearGradient(track.left(), 0, track.right(), 0)
                lg.setColorAt(0, acc); lg.setColorAt(1, mix(acc, theme.accent_alt, 0.65))
                p.setBrush(QBrush(lg))
            p.drawRoundedRect(QRectF(track.left(), track.top(), max(h, fw), h), h / 2, h / 2)
        if self._marker is not None:
            mf = (self._marker - self._min) / max(1, self._max - self._min)
            mx = track.left() + track.width() * mf
            p.setBrush(with_alpha(pal.text, 120))
            p.drawRoundedRect(QRectF(mx - 1, cy - h / 2 - 2, 2, h + 4), 1, 1)
        if active and self.isEnabled():
            if self._hover_x >= 0 and not self._drag:
                hx = max(t.left(), min(t.right(), self._hover_x))
                p.setBrush(with_alpha("#FFFFFF", 60))
                p.drawRoundedRect(QRectF(hx - 1, cy - 4, 2, 8), 1, 1)
            hx = track.left() + fw
            halo = QRadialGradient(QPointF(hx, cy), 10)
            halo.setColorAt(0, with_alpha(fill_color, 110)); halo.setColorAt(1, with_alpha(fill_color, 0))
            p.setBrush(QBrush(halo)); p.drawEllipse(QPointF(hx, cy), 10, 10)
            p.setBrush(QColor("#FFFFFF")); p.drawEllipse(QPointF(hx, cy), 4.5, 4.5)
        p.end()


class SeekBar(ModernSlider):
    """İlerleme çubuğu (ms). Üstüne gelince anlık zaman balonu gösterir."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 1, 0, formatter=format_time, bubble=True, parent=parent)
        self.setEnabled(False)


class VolumeSlider(ModernSlider):
    """%0–200 aralıklı ses kaydırıcısı; %100 işaretli, üstü turuncu uyarı rengi."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 200, 80, formatter=lambda v: f"%{v}", bubble=True,
                         marker=100, warn_above=100, parent=parent)
        self.setFixedWidth(70)


# ─────────────────────────────────────────────────────────────────────────────
class PlayButton(QAbstractButton):
    """Kompakt ve şık oynat/duraklat düğmesi (34×34 px)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._playing = False
        self._hover = False
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip("Oynat / Duraklat (Boşluk)")
        theme.changed.connect(self.update)

    def set_playing(self, on: bool) -> None:
        self._playing = on; self.update()

    def enterEvent(self, e) -> None:  # noqa: N802
        self._hover = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._hover = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        scale = 0.95 if self.isDown() else 1.0
        r = 14.5 * scale
        glow = QRadialGradient(c, 17)
        glow.setColorAt(0.45, with_alpha(theme.accent, 100 if self._hover else 60)); glow.setColorAt(1, with_alpha(theme.accent, 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(glow)); p.drawEllipse(c, 17, 17)
        circle = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        g = QLinearGradient(circle.topLeft(), circle.bottomRight())
        top = theme.accent_hover if self._hover else mix(theme.accent, "#FFFFFF", 0.14)
        g.setColorAt(0, top); g.setColorAt(1, theme.accent_pressed if self.isDown() else mix(theme.accent, theme.accent_alt, 0.5))
        p.setBrush(QBrush(g)); p.drawEllipse(circle)
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255, 255, 255, 60), 1)); p.drawEllipse(circle.adjusted(.5, .5, -.5, -.5))
        pm = icon_pixmap("pause" if self._playing else "play", theme.on_accent, 16)
        p.drawPixmap(QPointF(c.x() - 8, c.y() - 8), pm)
        p.end()


class _Divider(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(1, 14)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self); p.fillRect(self.rect(), with_alpha(theme.p.text, 30)); p.end()


class _Scrim(QWidget):
    """Videonun altında, çubuğun arkasında hafif sinematik karartma."""
    HEIGHT = 110

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.fx = QGraphicsOpacityEffect(self); self.fx.setOpacity(1.0); self.setGraphicsEffect(self.fx)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(0, 0, 0, 0)); g.setColorAt(0.55, QColor(0, 0, 0, 70)); g.setColorAt(1, QColor(0, 0, 0, 170))
        p.fillRect(self.rect(), QBrush(g)); p.end()


# ─────────────────────────────────────────────────────────────────────────────
class ControlBar(QWidget):
    playPauseClicked = Signal()
    previousClicked = Signal()
    nextClicked = Signal()
    stopClicked = Signal()
    skipRequested = Signal(int)            # ±10_000 ms
    seekRequested = Signal(int)            # ms (sürüklerken sürekli)
    volumeChanged = Signal(int)            # 0..200
    mutedChanged = Signal(bool)
    speedChanged = Signal(float)
    subtitleSelected = Signal(int)         # -1: kapalı
    subtitleFileRequested = Signal()
    audioTrackSelected = Signal(int)
    screenshotClicked = Signal()
    pipClicked = Signal()
    playlistToggled = Signal(bool)
    fullscreenToggled = Signal(bool)
    visibilityChanged = Signal(bool)       # imleci gizlemek için

    HIDE_DELAY_MS = 2500
    SH = 8                       # ince gölge payı
    BAR_H = 62                   # kompakt çubuk yüksekliği

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ControlBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setMinimumWidth(560 + 2 * self.SH)
        self.setFixedHeight(self.BAR_H + 2 * self.SH)
        self._scrim: _Scrim | None = None
        self._host: QWidget | None = None
        self._playing = False
        self._muted = False
        self._duration = 0
        self._speed = 1.0
        self._sub_current = -1
        self._audio_current = 0
        self._autohide = True
        self._shown = True
        self._max_width = 860
        self._bottom = 12

        # -- 1. satır: ilerleme ------------------------------------------------
        self.elapsed = QLabel("0:00"); self.elapsed.setObjectName("TimeLabel"); self.elapsed.setProperty("tone", "strong")
        self.remaining = QLabel("-0:00"); self.remaining.setObjectName("TimeLabel")
        self.elapsed.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.remaining.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        fm = self.elapsed.fontMetrics()
        for lbl in (self.elapsed, self.remaining):
            lbl.setMinimumWidth(fm.horizontalAdvance("-0:00:00") + 4)
            lbl.setStyleSheet("font-size: 11px;")
        self.seek = SeekBar()
        self.seek.userValueChanged.connect(self.seekRequested)
        self.seek.valueChanged.connect(lambda _v: self._update_time_labels())
        row1 = QHBoxLayout(); row1.setSpacing(6); row1.setContentsMargins(0, 0, 0, 0)
        row1.addWidget(self.elapsed); row1.addWidget(self.seek, 1); row1.addWidget(self.remaining)

        # -- 2. satır: sol oynatma grubu (kompakt 28px) ------------------------
        self.btn_prev = IconButton("prev", "Önceki (PgUp)", 28, 15)
        self.btn_back = IconButton("back10", "10 sn geri (←)", 28, 16)
        self.btn_play = PlayButton()
        self.btn_fwd = IconButton("fwd10", "10 sn ileri (→)", 28, 16)
        self.btn_next = IconButton("next", "Sonraki (PgDn)", 28, 15)
        self.btn_stop = IconButton("stop", "Durdur (S)", 28, 14)
        self.btn_prev.clicked.connect(self.previousClicked)
        self.btn_next.clicked.connect(self.nextClicked)
        self.btn_stop.clicked.connect(self.stopClicked)
        self.btn_back.clicked.connect(lambda: self.skipRequested.emit(-10_000))
        self.btn_fwd.clicked.connect(lambda: self.skipRequested.emit(10_000))
        self.btn_play.clicked.connect(self.playPauseClicked)

        # -- ses grubu ---------------------------------------------------------------
        self.btn_vol = IconButton("volume_high", "Sessiz (M)", 28, 16)
        self.btn_vol.clicked.connect(self._toggle_mute)
        self.volume = VolumeSlider()
        self.volume.valueChanged.connect(self._on_volume)
        self.vol_label = QLabel("%80"); self.vol_label.setObjectName("TimeLabel")
        self.vol_label.setStyleSheet("font-size: 11px;")
        self.vol_label.setMinimumWidth(self.vol_label.fontMetrics().horizontalAdvance("%200") + 4)

        # -- sağ araç grubu ----------------------------------------------------------
        self.btn_speed = IconButton("", "Oynatma hızı", (48, 24), 0, text="1.0x", variant="pill")
        self.btn_subs = IconButton("subtitles", "Altyazı", 28, 16)
        self.btn_audio = IconButton("audio_track", "Ses izi", 28, 16)
        self.btn_shot = IconButton("camera", "Ekran görüntüsü (Ctrl+S)", 28, 16)
        self.btn_pip = IconButton("pip", "Mini oynatıcı", 28, 16)
        self.btn_list = IconButton("playlist", "Çalma listesi (P)", 28, 16, checkable=True)
        self.btn_full = IconButton("fullscreen", "Tam ekran (F)", 28, 16, checkable=True)
        self.speed_menu, self.sub_menu, self.audio_menu = make_menu(self), make_menu(self), make_menu(self)
        self.btn_speed.attach_menu(self.speed_menu, up=True)
        self.btn_subs.attach_menu(self.sub_menu, up=True)
        self.btn_audio.attach_menu(self.audio_menu, up=True)
        self.btn_shot.clicked.connect(self.screenshotClicked)
        self.btn_pip.clicked.connect(self.pipClicked)
        self.btn_list.toggled.connect(self.playlistToggled)
        self.btn_full.toggled.connect(self._on_fullscreen_toggled)
        self._rebuild_speed_menu()
        self.set_subtitle_tracks([], -1)
        self.set_audio_tracks([], 0)

        row2 = QHBoxLayout(); row2.setSpacing(2); row2.setContentsMargins(0, 0, 0, 0)
        for w in (self.btn_prev, self.btn_back, self.btn_play, self.btn_fwd, self.btn_next, self.btn_stop):
            row2.addWidget(w)
        row2.addSpacing(8); row2.addWidget(_Divider()); row2.addSpacing(8)
        row2.addWidget(self.btn_vol); row2.addWidget(self.volume); row2.addSpacing(4); row2.addWidget(self.vol_label)
        row2.addStretch(1)
        row2.addWidget(self.btn_speed); row2.addSpacing(4)
        for w in (self.btn_subs, self.btn_audio, self.btn_shot, self.btn_pip):
            row2.addWidget(w)
        row2.addSpacing(6); row2.addWidget(_Divider()); row2.addSpacing(6)
        row2.addWidget(self.btn_list); row2.addWidget(self.btn_full)

        root = QVBoxLayout(self)
        sh = self.SH
        root.setContentsMargins(14 + sh, 6 + sh, 14 + sh, 6 + sh); root.setSpacing(2)
        root.addLayout(row1); root.addLayout(row2)

        # -- otomatik gizleme ------------------------------------------------------------
        self._effect = QGraphicsOpacityEffect(self); self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(200); self._fade.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._fade.finished.connect(self._on_fade_finished)
        self._effect.opacityChanged.connect(self._sync_scrim)
        self._timer = QTimer(self); self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._maybe_hide)
        self._quick_hide_timer = QTimer(self); self._quick_hide_timer.setSingleShot(True)
        self._quick_hide_timer.timeout.connect(self._maybe_hide)
        theme.changed.connect(self._on_theme_changed)
        self._on_volume(self.volume.value())

    # ── dış API ──────────────────────────────────────────────────────────────
    def set_duration(self, ms: int) -> None:
        self._duration = max(0, int(ms))
        self.seek.setRange(0, max(1, self._duration))
        self.seek.setEnabled(self._duration > 0)
        self._update_time_labels()

    def set_position(self, ms: int) -> None:
        if not self.seek.isDragging():
            self.seek.blockSignals(True); self.seek.setValue(int(ms)); self.seek.blockSignals(False)
            self.seek.update()
            self._update_time_labels()

    def set_buffered(self, ms: int) -> None:
        self.seek.set_buffered(ms)

    def set_playing(self, on: bool) -> None:
        self._playing = on
        self.btn_play.set_playing(on)
        self.poke()

    def set_volume(self, v: int) -> None:
        self.volume.setValue(v)

    def set_muted(self, on: bool) -> None:
        self._muted = on; self._refresh_volume_ui()

    def set_speed(self, v: float) -> None:
        self._speed = v
        self.btn_speed.set_label(_speed_text(v)); self._rebuild_speed_menu()

    def set_subtitle_tracks(self, tracks: list[tuple[str, int]], current: int = -1) -> None:
        self._sub_current = current
        entries = [("Kapalı", -1)] + [(n, i) for n, i in tracks]
        populate_choice_menu(self.sub_menu, entries, current, self._pick_sub)
        self.sub_menu.addSeparator()
        self.sub_menu.addAction("Altyazı Dosyası Yükle…").triggered.connect(self.subtitleFileRequested)

    def set_audio_tracks(self, tracks: list[tuple[str, int]], current: int = 0) -> None:
        self._audio_current = current
        entries = tracks or [("Varsayılan ses izi", 0)]
        populate_choice_menu(self.audio_menu, entries, current, self._pick_audio)
        self.btn_audio.setEnabled(bool(tracks))

    def set_playlist_checked(self, on: bool) -> None:
        self.btn_list.blockSignals(True); self.btn_list.setChecked(on); self.btn_list.blockSignals(False)

    def set_fullscreen_checked(self, on: bool) -> None:
        self.btn_full.blockSignals(True); self.btn_full.setChecked(on); self.btn_full.blockSignals(False)
        self.btn_full.set_icon_name("fullscreen_exit" if on else "fullscreen")

    def set_autohide_enabled(self, on: bool) -> None:
        self._autohide = on
        if on:
            self.poke()
        else:
            self._timer.stop(); self._quick_hide_timer.stop(); self._show_animated()

    # ── yüzen davranış ─────────────────────────────────────────────────────────
    def attach_to(self, host: QWidget, *, bottom_margin: int = 12, max_width: int = 860) -> None:
        """Çubuğu `host` üzerinde alt ortaya yerleştirir ve fare hareketini izler."""
        self._host, self._bottom, self._max_width = host, bottom_margin, max_width
        self.setParent(host)
        self._scrim = _Scrim(host)
        host.setMouseTracking(True)
        host.installEventFilter(self)
        QApplication.instance().installEventFilter(self)
        self._reposition()
        self.raise_(); self.show(); self.poke()

    def _reposition(self) -> None:
        h = self._host
        if h is None:
            return
        sh = self.SH
        w = max(self.minimumWidth() - 2 * sh, min(self._max_width, h.width() - 32))
        self.setGeometry((h.width() - w) // 2 - sh, h.height() - self.BAR_H - self._bottom - sh, w + 2 * sh, self.height())
        if self._scrim is not None:
            hh = min(_Scrim.HEIGHT, h.height())
            self._scrim.setGeometry(0, h.height() - hh, h.width(), hh)
            self._scrim.stackUnder(self)
        self.raise_()

    def enterEvent(self, e) -> None:  # noqa: N802
        self._quick_hide_timer.stop()
        self._timer.stop()
        self._show_animated()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        if self._autohide and self._playing and not self._is_interacting():
            self._quick_hide_timer.start(350)
        super().leaveEvent(e)

    def eventFilter(self, obj, ev) -> bool:  # noqa: N802
        h = self._host
        if h is not None:
            try:
                t = ev.type()
                if t == QEvent.Type.MouseMove and not isinstance(obj, QWidget):
                    return False
            except RuntimeError:
                return False

            if obj is h and t == QEvent.Type.Resize:
                self._reposition()
            elif t == QEvent.Type.MouseMove and isinstance(obj, QWidget) and h.isVisible() \
                    and (obj is h or h.isAncestorOf(obj)):
                # Fare çubuğun veya alt tetikleme bölgesinin üzerinde mi kontrol et
                global_pos = ev.globalPosition().toPoint()
                host_pos = h.mapFromGlobal(global_pos)
                hover_zone_top = h.height() - (self.BAR_H + self._bottom + 25)

                if host_pos.y() >= hover_zone_top or self.underMouse():
                    self._quick_hide_timer.stop()
                    self._show_animated()
                    if self._autohide and self._playing:
                        self._timer.start(self.HIDE_DELAY_MS)
                elif self._shown and self._autohide and self._playing:
                    # Fare video alanına (yukarı) çıktıysa gecikmeksizin gizle
                    if not self._is_interacting() and not self._quick_hide_timer.isActive():
                        self._quick_hide_timer.start(350)
        return False

    def _is_interacting(self) -> bool:
        return (
            self.underMouse()
            or self.seek.isDragging()
            or self.volume.isDragging()
            or (QApplication.activePopupWidget() is not None)
        )

    def poke(self) -> None:
        """Fare/klavye etkinliği: çubuğu göster ve gizleme sayacını yeniden başlat."""
        if self._host is None or not self._host.isVisible():
            return
        self._show_animated()
        if self._autohide and self._playing:
            self._timer.start(self.HIDE_DELAY_MS)

    def _maybe_hide(self) -> None:
        if not (self._autohide and self._playing):
            return
        if self._is_interacting():
            self._timer.start(600)
            return
        self._fade.stop()
        self._fade.setStartValue(self._effect.opacity()); self._fade.setEndValue(0.0); self._fade.start()
        self._shown = False

    def _show_animated(self) -> None:
        if self._shown and self.isVisible() and self._effect.opacity() >= 0.99:
            return
        self._fade.stop()
        was_hidden = not self.isVisible()
        self.show(); self.raise_()
        self._fade.setStartValue(0.0 if was_hidden else self._effect.opacity())
        self._fade.setEndValue(1.0); self._fade.start()
        if not self._shown or was_hidden:
            self.visibilityChanged.emit(True)
        self._shown = True

    def _sync_scrim(self, v: float) -> None:
        if self._scrim is not None:
            self._scrim.fx.setOpacity(v)

    def showEvent(self, e) -> None:  # noqa: N802
        if self._scrim is not None:
            self._scrim.show(); self._scrim.stackUnder(self)
        super().showEvent(e)

    def hideEvent(self, e) -> None:  # noqa: N802
        if self._scrim is not None:
            self._scrim.hide()
        super().hideEvent(e)

    def _on_fade_finished(self) -> None:
        if not self._shown and self._effect.opacity() <= 0.01:
            self.hide(); self.visibilityChanged.emit(False)

    # ── iç mantık ────────────────────────────────────────────────────────────
    def _update_time_labels(self) -> None:
        pos = self.seek.value()
        self.elapsed.setText(format_time(pos))
        self.remaining.setText("-" + format_time(max(0, self._duration - pos)))

    def _toggle_mute(self) -> None:
        self._muted = not self._muted
        self._refresh_volume_ui(); self.mutedChanged.emit(self._muted)

    def _on_volume(self, v: int) -> None:
        if v > 0 and self._muted and self.volume.isDragging():
            self._muted = False; self.mutedChanged.emit(False)
        self._refresh_volume_ui(); self.volumeChanged.emit(v)

    def _refresh_volume_ui(self) -> None:
        v = self.volume.value()
        self.vol_label.setText(f"%{v}")
        self.volume.set_dimmed(self._muted)
        name = "volume_mute" if (self._muted or v == 0) else ("volume_low" if v < 50 else "volume_high")
        self.btn_vol.set_icon_name(name)

    def _rebuild_speed_menu(self) -> None:
        entries = [("Normal (1.0x)" if s == 1.0 else _speed_text(s), s) for s in SPEEDS]
        populate_choice_menu(self.speed_menu, entries, self._speed, self._pick_speed)

    def _pick_speed(self, s) -> None:
        self.set_speed(float(s)); self.speedChanged.emit(float(s))

    def _pick_sub(self, i) -> None:
        self._sub_current = int(i); self.subtitleSelected.emit(int(i))

    def _pick_audio(self, i) -> None:
        self._audio_current = int(i); self.audioTrackSelected.emit(int(i))

    def _on_fullscreen_toggled(self, on: bool) -> None:
        self.btn_full.set_icon_name("fullscreen_exit" if on else "fullscreen")
        self.fullscreenToggled.emit(on)

    def _on_theme_changed(self) -> None:
        self._rebuild_speed_menu()
        self.update()

    # ── boyama: cam yüzey ──────────────────────────────────────────────────────
    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sh = self.SH
        r = QRectF(self.rect()).adjusted(sh, sh, -sh, -sh)
        soft_shadow(p, r, 14, layers=6, dy=6, alpha=40 if theme.mode == "dark" else 24, spread=1.4)
        paint_glass(p, r, 14, alpha=236 if theme.mode == "dark" else 244)
        p.end()
