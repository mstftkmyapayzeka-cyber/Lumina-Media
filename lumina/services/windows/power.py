"""Windows Güç Yönetimi (Video oynatılırken ekranın ve sistemin uyumasını engeller)."""
from __future__ import annotations

import ctypes
import logging

log = logging.getLogger(__name__)

# Windows SetThreadExecutionState bayrakları
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

class WindowsPowerManager:
    """Oynatma süresince Windows ekran koruyucuyu ve uyku modunu engeller."""

    def __init__(self):
        self._is_preventing = False

    def prevent_sleep(self, enabled: bool = True) -> None:
        if enabled and not self._is_preventing:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                )
                self._is_preventing = True
                log.debug("Windows uyku modu engellendi.")
            except Exception as exc:
                log.warning("SetThreadExecutionState başarısız: %s", exc)
        elif not enabled and self._is_preventing:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                self._is_preventing = False
                log.debug("Windows uyku modu serbest bırakıldı.")
            except Exception as exc:
                log.warning("SetThreadExecutionState serbest bırakma başarısız: %s", exc)
