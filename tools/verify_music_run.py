"""Müzik modu ve görselleştirici geçişini doğrulayan otomatik test."""
import os
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from lumina.core.media_item import MediaItem
from lumina.services.settings import Settings
from lumina.ui.main_window import MainWindow

app = QApplication(sys.argv)
settings = Settings()
win = MainWindow(settings)
win.show()

test_audio = os.path.abspath("test_media/muzik.mp3")
item = MediaItem(path=test_audio)
win.playlist.add_items([item])
win.playlist.set_current_index(0)
win.play_item(item)

def check_playback():
    print("Müzik Oynatma durumu:", win.engine.state)
    print("Görünüm indisi (AudioView beklenir=2):", win.content_stack.currentIndex())
    print("Görselleştirici aktif mi:", win.audio_view.visualizer._is_playing)
    assert win.content_stack.currentIndex() == 2  # AudioView
    assert win.audio_view.visualizer._is_playing is True
    win.engine.stop()
    win.engine.shutdown()
    win.close()
    app.quit()
    print("Müzik modu doğrulama BAŞARILI!")

QTimer.singleShot(2500, check_playback)
app.exec()
