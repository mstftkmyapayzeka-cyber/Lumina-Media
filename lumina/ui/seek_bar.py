"""Gelişmiş Arama Çubuğu (SeekBar) - Hover zaman balonu ve hassas sarma desteği."""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QLabel, QWidget

def format_time_ms(ms: int) -> str:
    if ms < 0:
        ms = 0
    total_sec = ms // 1000
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    seconds = total_sec % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

class TimeTooltip(QLabel):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet("""
            QLabel {
                background-color: #20242C;
                color: #FFFFFF;
                border: 1px solid #383F4E;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: 600;
            }
        """)

class SeekBar(QWidget):
    seekRequested = Signal(int)  # ms cinsinden istenen hedef konum
    hoverChanged = Signal(int, QPoint)  # ms ve global koordinat (önizleme resmi için)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        self._duration: int = 0
        self._position: int = 0
        self._is_dragging: bool = False
        self._hover_x: int = -1
        self._accent_color: str = "#3B82F6"

        self._tooltip = TimeTooltip(self)
        self._tooltip.hide()

    def set_accent_color(self, color_hex: str) -> None:
        self._accent_color = color_hex
        self.update()

    def set_duration(self, ms: int) -> None:
        self._duration = max(0, ms)
        self.update()

    def set_position(self, ms: int) -> None:
        if not self._is_dragging:
            self._position = max(0, min(self._duration, ms))
            self.update()

    def duration(self) -> int:
        return self._duration

    def position(self) -> int:
        return self._position

    def _x_to_ms(self, x: int) -> int:
        if self.width() <= 0 or self._duration <= 0:
            return 0
        ratio = max(0.0, min(1.0, x / self.width()))
        return int(ratio * self._duration)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            target_ms = self._x_to_ms(int(event.position().x()))
            self._position = target_ms
            self.seekRequested.emit(target_ms)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        x = int(event.position().x())
        self._hover_x = x
        hover_ms = self._x_to_ms(x)

        if self._is_dragging:
            self._position = hover_ms
            self.seekRequested.emit(hover_ms)

        # Tooltip konumlandır ve göster
        if self._duration > 0:
            self._tooltip.setText(format_time_ms(hover_ms))
            self._tooltip.adjustSize()
            global_pos = self.mapToGlobal(QPoint(x, 0))
            self._tooltip.move(global_pos.x() - self._tooltip.width() // 2, global_pos.y() - 28)
            self._tooltip.show()
            self.hoverChanged.emit(hover_ms, global_pos)

        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover_x = -1
        self._tooltip.hide()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        is_hovered = self._hover_x >= 0 or self._is_dragging
        bar_height = 6 if is_hovered else 4
        bar_y = (h - bar_height) // 2

        # Arka plan oluk
        painter.setBrush(QColor("#2B303B"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, bar_y, w, bar_height, bar_height // 2, bar_height // 2)

        # İlerleme dolgusu
        if self._duration > 0:
            progress_ratio = self._position / self._duration
            progress_w = int(w * progress_ratio)

            painter.setBrush(QColor(self._accent_color))
            painter.drawRoundedRect(0, bar_y, progress_w, bar_height, bar_height // 2, bar_height // 2)

            # Tutamaç (Handle) - hover veya sürükleme durumunda belirir
            if is_hovered:
                handle_radius = 6
                handle_x = progress_w
                painter.setBrush(QColor("#FFFFFF"))
                painter.drawEllipse(QPoint(handle_x, h // 2), handle_radius, handle_radius)
