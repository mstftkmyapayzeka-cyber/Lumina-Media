"""Tekil Uygulama Örneği (Single Instance) - İkinci kez açılan dosyaları mevcut pencereye aktarır."""
from __future__ import annotations

import json
import logging
from typing import List, Optional
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger(__name__)

SERVER_NAME = "LuminaPlayerSingleInstanceSocket"

class SingleInstanceController(QObject):
    messageReceived = Signal(list)  # yeni açılan dosya yolları listesi

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._server: Optional[QLocalServer] = None

    def try_lock(self, args: List[str]) -> bool:
        """Eğer başka bir kopya çalışıyorsa argümanları ona yollar ve False döner.
        İlk kopya ise sunucuyu başlatır ve True döner.
        """
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)

        # Başka bir örnek var mı kontrol et
        if socket.waitForConnected(500):
            # Mevcut örneğe argümanları gönder
            data = json.dumps(args).encode("utf-8")
            socket.write(data)
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            log.info("Argümanlar çalışan mevcut örneğe iletildi.")
            return False

        # İlk örnek: Sunucu soketini oluştur
        self._server = QLocalServer(self)
        # Eski kalan soketi temizle
        QLocalServer.removeServer(SERVER_NAME)
        if not self._server.listen(SERVER_NAME):
            log.warning("Yerel soket sunucusu dinlenemedi: %s", self._server.errorString())
        else:
            self._server.newConnection.connect(self._on_new_connection)
            log.info("Tekil örnek sunucusu başlatıldı.")

        return True

    def _on_new_connection(self) -> None:
        if not self._server:
            return
        client = self._server.nextPendingConnection()
        if not client:
            return

        def _on_ready_read():
            raw_data = client.readAll().data().decode("utf-8", errors="ignore")
            try:
                paths = json.loads(raw_data)
                if isinstance(paths, list):
                    self.messageReceived.emit(paths)
            except Exception:
                pass
            client.deleteLater()

        client.readyRead.connect(_on_ready_read)
