"""
Lumina Player — audio_view.py
=============================
Ses dosyası çalarken devreye giren görünüm: ortada büyük yuvarlak köşeli albüm kapağı,
parça adı + sanatçı ve arka planda hafif spektrum/dalga görselleştirmesi.
Gerçek FFT verisi için `set_levels([...0..1])` çağırın; verilmezse çalarken yumuşak
bir demo dalgası üretilir.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from lumina.ui.theme import icon_pixmap, paint_aurora, soft_shadow, theme, tile_colors, ui_font, with_alpha

BARS = 56


class AudioView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AudioView")
        self._title, self._artist, self._album = "", "", ""
        self._cover: QPixmap | None = None
        self._playing = False
        self._ext_levels: list[float] | None = None
        self._levels = [0.05] * BARS
        self._phase = 0.0
        self._timer = QTimer(self); self._timer.setInterval(33); self._timer.timeout.connect(self._tick)
        theme.changed.connect(self.update)

    # -- API --------------------------------------------------------------------------
    def set_metadata(self, title: str, artist: str = "", album: str = "", cover: QPixmap | None = None) -> None:
        self._title, self._artist, self._album, self._cover = title, artist, album, cover
        self.update()

    def set_playing(self, on: bool) -> None:
        self._playing = on
        if on: self._timer.start()
        self.update()

    def set_levels(self, levels: list[float] | None) -> None:
        self._ext_levels = list(levels) if levels else None

    # -- animasyon ----------------------------------------------------------------------
    def _tick(self) -> None:
        self._phase += 0.07
        for i in range(BARS):
            if self._ext_levels:
                src = self._ext_levels[int(i * len(self._ext_levels) / BARS)]
            elif self._playing:
                x = i / BARS
                src = (0.5 + 0.5 * math.sin(self._phase * 1.7 + x * 9)) * (0.55 + 0.45 * math.sin(self._phase * 0.9 + x * 3.1))
                src = 0.12 + 0.8 * src * (1 - 0.55 * abs(x - 0.35))
            else:
                src = 0.04
            self._levels[i] += (max(0.02, min(1.0, src)) - self._levels[i]) * 0.28
        if not self._playing and max(self._levels) < 0.06:
            self._timer.stop()
        self.update()

    # -- boyama -----------------------------------------------------------------------------
    def paintEvent(self, _e) -> None:  # noqa: N802
        pal, acc = theme.p, theme.accent
        W, H = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        p.fillRect(self.rect(), QColor(pal.window))
        paint_aurora(p, QRectF(self.rect()), 1.0)

        cover = max(120.0, min(300.0, H * 0.40, W * 0.5))
        cx, top = W / 2, max(28.0, H * 0.10)
        ctr = QPointF(cx, top + cover / 2)
        # kapağın etrafında yayılan ışık halkaları (çalarken genliğe duyarlı)
        energy = sum(self._levels[:12]) / 12 if self._playing else 0.0
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i, (k, a0) in enumerate(((1.16, 34), (1.38, 18))):
            p.setPen(QPen(with_alpha(acc, int(a0 * (0.6 + 0.8 * energy))), 1.2))
            r = cover * k * (1 + 0.025 * energy * (i + 1))
            p.drawRoundedRect(QRectF(ctr.x() - r / 2, ctr.y() - r / 2, r, r), r * 0.14, r * 0.14)

        # spektrum: kontrol çubuğunun üstünde biten yuvarlak uçlu çubuklar
        base = H - 132.0
        zone = max(40.0, H * 0.24)
        bw = W / BARS
        grad = QLinearGradient(0, base, 0, base - zone)
        grad.setColorAt(0, with_alpha(theme.accent_alt, 170)); grad.setColorAt(1, with_alpha(acc, 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(grad))
        for i, lv in enumerate(self._levels):
            h = max(3.0, lv * zone)
            p.drawRoundedRect(QRectF(i * bw + bw * 0.24, base - h, bw * 0.52, h), bw * 0.26, bw * 0.26)
        path = QPainterPath(QPointF(0, base - self._levels[0] * zone))
        for i, lv in enumerate(self._levels):
            path.lineTo(i * bw + bw / 2, base - lv * zone - 2)
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(with_alpha(acc, 200), 1.5)); p.drawPath(path)

        # albüm kapağı
        r = QRectF(cx - cover / 2, top, cover, cover)
        rad = cover * 0.12
        soft_shadow(p, r, rad, layers=8, dy=22, alpha=60 if theme.mode == "dark" else 34, spread=2.4)
        clip = QPainterPath(); clip.addRoundedRect(r, rad, rad)
        p.save(); p.setClipPath(clip)
        dpr = p.device().devicePixelRatioF()
        if self._cover is not None and not self._cover.isNull():
            sc = self._cover.scaled(int(cover * dpr), int(cover * dpr), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                    Qt.TransformationMode.SmoothTransformation)
            sc.setDevicePixelRatio(dpr)
            ox = (sc.width() / dpr - cover) / 2; oy = (sc.height() / dpr - cover) / 2
            p.drawPixmap(QPointF(r.left() - ox, r.top() - oy), sc)
        else:
            c1, c2 = tile_colors(self._title or "lumina")
            lg = QLinearGradient(r.topLeft(), r.bottomRight()); lg.setColorAt(0, c1); lg.setColorAt(1, c2)
            p.fillRect(r, QBrush(lg))
            hl = QRadialGradient(QPointF(r.left() + cover * 0.25, r.top() + cover * 0.15), cover * 0.9)
            hl.setColorAt(0, QColor(255, 255, 255, 90)); hl.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillRect(r, QBrush(hl))
            sz = int(cover * 0.34)
            p.drawPixmap(QPointF(r.center().x() - sz / 2, r.center().y() - sz / 2), icon_pixmap("music", QColor(255, 255, 255, 235), sz))
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(255, 255, 255, 40), 1)); p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), rad, rad)

        # metinler
        ty = r.bottom() + 30
        maxw = int(min(W - 48, 560))

        def line(text: str, font: QFont, color: QColor, y: float) -> float:
            fm = QFontMetrics(font)
            p.setFont(font); p.setPen(color)
            p.drawText(QRectF(cx - maxw / 2, y, maxw, fm.height() + 2), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                       fm.elidedText(text, Qt.TextElideMode.ElideRight, maxw))
            return y + fm.height() + 6
        ty = line(self._title or "Çalan parça yok", ui_font(26, QFont.Weight.DemiBold, -1.0), QColor(pal.text), ty)
        if self._artist: ty = line(self._artist, ui_font(15, QFont.Weight.Medium), QColor(pal.text2), ty)
        if self._album: line(self._album, ui_font(12), QColor(pal.text2), ty)
        p.end()
