"""
Lumina Player — welcome_view.py
===============================
Video açık değilken gösterilen karşılama ekranı.

Tasarım fikri: tek ışık kaynağı. Logo, halka halka yayılan yumuşak bir ışığın merkezidir;
arkadaki aurora aynı vurgu renginden türer. Eylem kartları mat cam yüzeydir, üzerine
gelince yükselir ve kendi ışığını yakar (ikon karosu dolar, kenarlık parlar).
"""
from __future__ import annotations

from PySide6.QtCore import (
    Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QVariantAnimation, Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from lumina.ui.theme import (
    icon_pixmap, mix, paint_aurora, paint_glass, paint_logo, soft_shadow, theme, ui_font, with_alpha,
)

CARD_W, CARD_H, LIFT = 165, 115, 6
CARD_GAP = 16
ROW_W = CARD_W * 3 + CARD_GAP * 2
PAD = CARD_GAP // 2          # kartın etrafındaki gölge payı (komşu kartlarla birleşince boşluk = CARD_GAP)
TOP = 4
BOTTOM = 24


class LogoMark(QWidget):
    """Işık halkalarıyla çevrili Lumina simgesi; halkalar 3.6 sn'de yavaşça yayılıp solar."""

    def __init__(self, size: int = 104, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = size
        self._t = 0.0
        self.setFixedSize(int(size * 2.6), int(size * 1.9))
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=3600, loopCount=-1)
        self._anim.valueChanged.connect(self._tick)
        theme.changed.connect(self.update)

    def _tick(self, v) -> None:
        self._t = float(v); self.update()

    def showEvent(self, e) -> None:  # noqa: N802
        self._anim.start(); super().showEvent(e)

    def hideEvent(self, e) -> None:  # noqa: N802
        self._anim.stop(); super().hideEvent(e)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() * 0.5)
        s = self._s
        dark = theme.mode == "dark"
        # yayılan ışık halkaları (iki tane, yarım faz farklı)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for off in (0.0, 0.5):
            t = (self._t + off) % 1.0
            r = s * (0.62 + 0.95 * t)
            a = int((1 - t) ** 1.8 * (70 if dark else 55))
            p.setPen(QPen(with_alpha(theme.accent, a), 1.2)); p.drawEllipse(c, r, r)
        # merkez ışıması
        r = s * 1.05
        g = QRadialGradient(c, r)
        g.setColorAt(0, with_alpha(theme.accent, 120 if dark else 90))
        g.setColorAt(0.5, with_alpha(theme.accent_alt, 34)); g.setColorAt(1, with_alpha(theme.accent, 0))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(c, r, r)
        # logonun altına renkli gölge
        soft_shadow(p, QRectF(c.x() - s / 2 + 6, c.y() - s / 2 + 8, s - 12, s - 12), s * 0.26, layers=6, dy=12,
                    alpha=60 if dark else 34, color=theme.accent_alt.darker(150))
        paint_logo(p, QRectF(c.x() - s / 2, c.y() - s / 2, s, s))
        p.end()


class ActionCard(QWidget):
    """165×115 eylem kartı: mat cam; hover'da 6 px yükselir, ikon karosu dolar, kenarlık parlar."""

    clicked = Signal()

    def __init__(self, icon_name: str, title: str, desc: str, shortcut: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon, self._title, self._desc, self._shortcut = icon_name, title, desc, shortcut
        self._lift = 0.0
        self._down = False
        self._kbd = False
        self.setFixedSize(CARD_W + 2 * PAD, TOP + LIFT + CARD_H + BOTTOM)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._anim = QPropertyAnimation(self, b"lift", self)
        self._anim.setDuration(180); self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        theme.changed.connect(self.update)

    def _get_lift(self) -> float: return self._lift
    def _set_lift(self, v: float) -> None:
        self._lift = v; self.update()
    lift = Property(float, _get_lift, _set_lift)

    def _go(self, target: float) -> None:
        self._anim.stop(); self._anim.setStartValue(self._lift); self._anim.setEndValue(target); self._anim.start()

    def enterEvent(self, e) -> None:  # noqa: N802
        self._go(float(LIFT)); super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._go(0.0); super().leaveEvent(e)

    def focusInEvent(self, e) -> None:  # noqa: N802
        self._kbd = e.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)
        self.update(); super().focusInEvent(e)

    def focusOutEvent(self, e) -> None:  # noqa: N802
        self._kbd = False; self.update(); super().focusOutEvent(e)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._down = True; self.update()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        was, self._down = self._down, False
        self.update()
        if was and e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _e) -> None:  # noqa: N802
        pal, acc = theme.p, theme.accent
        t = self._lift / LIFT
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        card = QRectF(PAD, TOP + LIFT - self._lift + (1.5 if self._down else 0), CARD_W, CARD_H)
        # altında yanan ışık
        if t > 0.01:      # yatay yassı ışık havuzu (widget sınırında sıfırlanır)
            p.save(); p.translate(card.center().x(), card.bottom() + 2); p.scale(1.0, 0.26)
            g = QRadialGradient(QPointF(0, 0), self.width() / 2)
            g.setColorAt(0, with_alpha(acc, int(95 * t))); g.setColorAt(1, with_alpha(acc, 0))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(QPointF(0, 0), self.width() / 2, self.width() / 2)
            p.restore()
        soft_shadow(p, card, 16, layers=4, dy=5 + 4 * t, alpha=int(16 + 14 * t), spread=2.0)
        paint_glass(p, card, 16, alpha=255, tint=QColor(pal.hover if t > 0.5 else pal.surface))
        if t > 0.01:   # parlayan kenarlık: üstte tam, altta sönük
            edge = QLinearGradient(card.topLeft(), card.bottomLeft())
            edge.setColorAt(0, with_alpha(acc, int(255 * t))); edge.setColorAt(1, with_alpha(acc, int(110 * t)))
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QBrush(edge), 1.3))
            p.drawRoundedRect(card.adjusted(.6, .6, -.6, -.6), 16, 16)
        if self._kbd:
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(with_alpha(acc, 160), 2))
            p.drawRoundedRect(card.adjusted(-3, -3, 3, 3), 19, 19)
        # ikon karosu: soluk → dolu
        tile = QRectF(card.left() + 16, card.top() + 16, 42, 42)
        fill = QLinearGradient(tile.topLeft(), tile.bottomRight())
        fill.setColorAt(0, mix(with_alpha(acc, 46), theme.accent_hover, t))
        fill.setColorAt(1, mix(with_alpha(acc, 30), theme.accent_alt, t))
        p.setPen(QPen(with_alpha(acc, int(70 * (1 - t))), 1)); p.setBrush(QBrush(fill)); p.drawRoundedRect(tile, 13, 13)
        glyph = mix(acc, theme.on_accent, t)
        p.drawPixmap(QPointF(tile.center().x() - 11, tile.center().y() - 11), icon_pixmap(self._icon, glyph, 22))
        # kısayol çipi
        f_chip = ui_font(10, QFont.Weight.DemiBold, 0.4); p.setFont(f_chip)
        cw = QFontMetrics(f_chip).horizontalAdvance(self._shortcut) + 14
        chip = QRectF(card.right() - 14 - cw, card.top() + 18, cw, 20)
        p.setPen(QPen(with_alpha(pal.text, 24), 1)); p.setBrush(with_alpha(pal.text, 14)); p.drawRoundedRect(chip, 10, 10)
        p.setPen(QColor(pal.text2)); p.drawText(chip, Qt.AlignmentFlag.AlignCenter, self._shortcut)
        # başlık + açıklama
        f_t, f_d = ui_font(14, QFont.Weight.DemiBold, -0.4), ui_font(11)
        p.setFont(f_t); p.setPen(QColor(pal.text))
        p.drawText(QRectF(card.left() + 16, card.top() + 67, CARD_W - 32, 22), Qt.AlignmentFlag.AlignVCenter, self._title)
        p.setFont(f_d); p.setPen(QColor(pal.text2))
        el = QFontMetrics(f_d).elidedText(self._desc, Qt.TextElideMode.ElideRight, CARD_W - 32)
        p.drawText(QRectF(card.left() + 16, card.top() + 89, CARD_W - 32, 18), Qt.AlignmentFlag.AlignVCenter, el)
        p.end()


class DropZone(QWidget):
    """Kesik çizgili bırakma alanı; sürükleme sırasında ışık yakar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active = False
        self.setFixedSize(ROW_W, 96)
        theme.changed.connect(self.update)

    def set_active(self, on: bool) -> None:
        if on != self._active:
            self._active = on; self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        pal, acc = theme.p, theme.accent
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(with_alpha(acc, 34) if self._active else with_alpha(pal.text, 7))
        p.drawRoundedRect(r, 18, 18)
        pen = QPen(acc if self._active else with_alpha(pal.text, 52), 1.5)
        pen.setDashPattern([4.0, 5.0]); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(r, 18, 18)
        f1, f2 = ui_font(14, QFont.Weight.DemiBold, -0.3), ui_font(11)
        t1 = "Video veya klasörleri buraya sürükleyip bırakın"
        t2 = "MP4, MKV, AVI, MOV, WEBM, MP3, FLAC ve daha fazlası"
        w1 = QFontMetrics(f1).horizontalAdvance(t1)
        total = 36 + 14 + w1
        x = (self.width() - total) / 2
        circ = QRectF(x, 20, 36, 36)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(with_alpha(acc, 60 if self._active else 34)); p.drawEllipse(circ)
        p.drawPixmap(QPointF(circ.center().x() - 10, circ.center().y() - 10),
                     icon_pixmap("download", acc if self._active else pal.text, 20))
        p.setFont(f1); p.setPen(QColor(pal.text))
        p.drawText(QRectF(x + 50, 19, w1 + 6, 38), Qt.AlignmentFlag.AlignVCenter, t1)
        p.setFont(f2); p.setPen(theme.accent_text if self._active else QColor(pal.text2))
        p.drawText(QRectF(0, 62, self.width(), 20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, t2)
        p.end()


class KeyHints(QWidget):
    """Klavye kısayol ipuçları: tuş kapağı + açıklama."""
    HINTS = (("Boşluk", "Oynat / Duraklat"), ("P", "Çalma listesi"), ("F", "Tam ekran"), ("M", "Sessiz"))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        theme.changed.connect(self.update)

    def paintEvent(self, _e) -> None:  # noqa: N802
        pal = theme.p
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        fk, fl = ui_font(10, QFont.Weight.DemiBold), ui_font(11)
        mk, ml = QFontMetrics(fk), QFontMetrics(fl)
        items = [(k, l, mk.horizontalAdvance(k) + 14, ml.horizontalAdvance(l)) for k, l in self.HINTS]
        total = sum(w + 8 + lw for _, _, w, lw in items) + 24 * (len(items) - 1)
        x = (self.width() - total) / 2
        for k, l, kw, lw in items:
            cap = QRectF(x, 5, kw, 20)
            p.setPen(QPen(with_alpha(pal.text, 34), 1)); p.setBrush(with_alpha(pal.text, 12)); p.drawRoundedRect(cap, 6, 6)
            p.setFont(fk); p.setPen(QColor(pal.text2)); p.drawText(cap, Qt.AlignmentFlag.AlignCenter, k)
            p.setFont(fl); p.setPen(QColor(pal.text2))
            p.drawText(QRectF(x + kw + 8, 5, lw + 4, 20), Qt.AlignmentFlag.AlignVCenter, l)
            x += kw + 8 + lw + 24
        p.end()


class WelcomeView(QWidget):
    openFileRequested = Signal()
    openFolderRequested = Signal()
    openUrlRequested = Signal()
    pathsDropped = Signal(list)       # yerel dosya/klasör yolları ya da http(s)/rtsp URL'leri

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._entered = False
        self.logo = LogoMark(104)
        title = QLabel("Lumina Player"); title.setProperty("role", "display")
        title.setFont(ui_font(40, QFont.Weight.DemiBold, -1.6)); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Her biçim, her ekranda. Başlamak için bir dosya, klasör ya da akış seçin.")
        sub.setProperty("role", "secondary"); sub.setFont(ui_font(14)); sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cards = [
            ActionCard("file", "Dosya Aç", "Video veya ses dosyası", "Ctrl+O"),
            ActionCard("folder", "Klasör Aç", "Tüm klasörü listeye ekle", "Ctrl+Shift+O"),
            ActionCard("link", "URL / Akış Aç", "HTTP, RTSP, HLS adresi", "Ctrl+U"),
        ]
        cards[0].clicked.connect(self.openFileRequested)
        cards[1].clicked.connect(self.openFolderRequested)
        cards[2].clicked.connect(self.openUrlRequested)
        self.cards = cards
        row_box = QWidget(); row_box.setFixedWidth(3 * (CARD_W + 2 * PAD))
        row = QHBoxLayout(row_box); row.setSpacing(0); row.setContentsMargins(0, 0, 0, 0)
        for c in cards: row.addWidget(c)
        self.drop = DropZone()

        self.content = QWidget()
        cl = QVBoxLayout(self.content); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)
        cl.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        cl.addSpacing(-30)
        cl.addWidget(title); cl.addSpacing(10); cl.addWidget(sub); cl.addSpacing(28)
        cl.addWidget(row_box, 0, Qt.AlignmentFlag.AlignHCenter); cl.addSpacing(-8)
        cl.addWidget(self.drop, 0, Qt.AlignmentFlag.AlignHCenter)
        self._fx = QGraphicsOpacityEffect(self.content); self._fx.setOpacity(0.0)
        self.content.setGraphicsEffect(self._fx)
        self._fade = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade.setDuration(520); self._fade.setStartValue(0.0); self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(lambda: self.content.setGraphicsEffect(None))

        lay = QVBoxLayout(self); lay.setContentsMargins(24, 24, 24, 20); lay.setSpacing(0)
        lay.addStretch(3); lay.addWidget(self.content, 0, Qt.AlignmentFlag.AlignHCenter); lay.addStretch(4)
        lay.addWidget(KeyHints())

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if not self._entered:                 # tek, tasarlanmış açılış: içerik yumuşakça belirir
            self._entered = True; self._fade.start()

    # -- sürükle-bırak: pencerenin her yeri hedef ---------------------------------------
    def dragEnterEvent(self, e) -> None:  # noqa: N802
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            self.drop.set_active(True); e.acceptProposedAction()

    def dragLeaveEvent(self, e) -> None:  # noqa: N802
        self.drop.set_active(False)

    def dropEvent(self, e) -> None:  # noqa: N802
        self.drop.set_active(False)
        paths: list[str] = []
        for u in e.mimeData().urls():
            paths.append(u.toLocalFile() if u.isLocalFile() else u.toString())
        if not paths and e.mimeData().hasText():
            t = e.mimeData().text().strip()
            if t.lower().startswith(("http://", "https://", "rtsp://")): paths.append(t)
        if paths:
            self.pathsDropped.emit(paths); e.acceptProposedAction()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.p.window))
        paint_aurora(p, QRectF(self.rect()), 1.0)
        # alt kenara doğru hafif vinyet
        g = QLinearGradient(0, self.height() * 0.6, 0, self.height())
        g.setColorAt(0, QColor(0, 0, 0, 0)); g.setColorAt(1, QColor(0, 0, 0, 70 if theme.mode == "dark" else 0))
        p.fillRect(self.rect(), QBrush(g))
        p.end()
