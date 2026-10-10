"""Klasör yükleme ve Çalma Listesi gösterimini uçtan uca doğrulayan test."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from lumina.services.settings import Settings
from lumina.ui.main_window import MainWindow

app = QApplication(sys.argv)
settings = Settings()
win = MainWindow(settings)
win.show()

# Test klasörünü yükle
test_folder = os.path.abspath("test_media")
win.playlist_panel.load_folder(test_folder)
win.set_playlist(True)

def verify():
    # 1. Panel açık olmalı
    assert win.playlist_panel.is_open(), "Çalma listesi paneli açık olmalı!"
    # 2. Klasör banner görünür olmalı
    assert win.playlist_panel.banner.isVisible(), "Klasör bilgi banner'ı görünür olmalı!"
    # 3. Öğeler çalma listesine yüklenmiş olmalı
    item_count = len(win.playlist_panel.model.items)
    print(f"Çalma listesindeki toplam video/medya sayısı: {item_count}")
    assert item_count > 0, "Klasördeki medyalar çalma listesine yüklenmiş olmalı!"
    # 4. View satır sayısı eşleşmeli
    assert win.playlist_panel.view.model().rowCount() == item_count, "Görünüm satır sayısı eşleşmeli!"
    print("Klasör yükleme ve Çalma Listesi görünümü %100 BAŞARILI!")
    win.engine.stop()
    win.engine.shutdown()
    win.close()
    app.quit()

# Tarama işlemi arka planda tamamlandıktan sonra (1.5 sn) doğrula
QTimer.singleShot(1800, verify)
app.exec()
