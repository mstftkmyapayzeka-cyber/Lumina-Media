"""Lumina Player uygulama girişi ve yaşam döngüsü yöneticisi."""
from __future__ import annotations

import os
import sys
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from lumina.core.media_item import MediaItem
from lumina.services.logger import install_exception_hooks, setup_logging
from lumina.services.settings import Settings
from lumina.services.single_instance import SingleInstanceController
from lumina.ui.main_window import MainWindow

def run_lumina(argv: List[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv

    # Günlük kaydı ve hata yakalayıcıları başlat
    log = setup_logging()
    install_exception_hooks()
    log.info("Lumina Player başlatılıyor...")

    # Yüksek DPI ve Windows ölçekleme desteği
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(argv)
    app.setApplicationName("Lumina Player")
    app.setOrganizationName("Lumina")

    # Komut satırından gelen dosya yolları
    cli_files = [arg for arg in argv[1:] if os.path.exists(arg) or arg.startswith(("http://", "https://"))]

    # Tekil Örnek (Single Instance) Kontrolü
    single_inst = SingleInstanceController()
    if not single_inst.try_lock(cli_files):
        log.info("Uygulama zaten çalışıyor. Dosyalar mevcut pencereye aktarıldı, çıkılıyor.")
        return 0

    settings = Settings()
    from lumina.ui.theme import theme
    mode = settings.get("ui.theme", "dark")
    accent = settings.get("ui.accent", "blue")
    theme.set_mode("dark" if mode != "light" else "light")
    theme.set_accent(accent)
    theme.apply(app)

    window = MainWindow(settings)

    # İkinci örnekten gelen dosya argümanlarını dinle
    single_inst.messageReceived.connect(lambda paths: _handle_remote_files(window, paths))

    window.show()

    # Eğer komut satırından dosya verildiyse hemen oynat
    if cli_files:
        _handle_remote_files(window, cli_files)

    exit_code = app.exec()

    # Çıkışta kaynakları temizle
    window.engine.shutdown()
    log.info("Lumina Player temiz bir şekilde kapatıldı.")
    return exit_code

def _handle_remote_files(window: MainWindow, paths: List[str]) -> None:
    if not paths:
        return
    window.handle_dropped_paths(paths)
    window.activateWindow()
    window.raise_()
