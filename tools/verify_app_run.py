"""Uygulamanın GUI ve oynatma akışının uçtan uca çalıştığını doğrulayan otomatik test."""
import os
import sys

# Proje kökünü sys.path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from lumina.core.media_item import MediaItem
from lumina.services.settings import Settings
from lumina.ui.main_window import MainWindow

app = QApplication(sys.argv)
settings = Settings()
win = MainWindow(settings)
win.show()

test_video = os.path.abspath("test_media/Dizi Bölüm 1.mp4")
item = MediaItem(path=test_video)
win.playlist_panel.add_items([item])
win.playlist_panel.activate(0)

def check_playback():
    print("Oynatma durumu:", win.engine.state)
    print("Görünüm indisi:", win.stack.currentIndex())
    print("Süre (ms):", win.engine.length())
    print("Ses düzeyi:", win.engine.volume())
    assert win.stack.currentIndex() == 1  # Video yüzeyi aktif
    win.engine.stop()
    win.engine.shutdown()
    win.close()
    app.quit()
    print("Uçtan uca doğrulama BAŞARILI!")

# 2 saniye sonra oynatma durumunu doğrula ve kapat
QTimer.singleShot(2500, check_playback)
app.exec()
