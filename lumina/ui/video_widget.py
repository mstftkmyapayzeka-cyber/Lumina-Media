"""Video yüzeyi bileşeni (libVLC HWND ev sahibi ve fare/sürükle-bırak etkileşimi)."""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QWidget

class VideoWidget(QWidget):
    doubleClicked = Signal()
    clicked = Signal()
    middleClicked = Signal()
    wheelScrolled = Signal(int)  # delta (+/- ses ayarı)
    mouseMoved = Signal(QPoint)
    filesDropped = Signal(list)  # bırakılan dosya/klasör yolları

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # libVLC doğrudan HWND'ye çizeceği için yerel pencere nitelikleri
        self.setAttribute(Qt.WA_NativeWindow)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: #000000;")

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
            event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
        elif event.button() == Qt.MiddleButton:
            self.middleClicked.emit()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.mouseMoved.emit(event.globalPosition().toPoint())
        event.accept()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta != 0:
            self.wheelScrolled.emit(delta)
            event.accept()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        paths: List[str] = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
