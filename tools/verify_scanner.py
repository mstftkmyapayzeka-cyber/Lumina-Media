"""Klasör tarama ve doğal sıralama testini doğrulayan otomatik test."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication
from lumina.core.scanner import FolderScanner

app = QCoreApplication(sys.argv)

folder = os.path.abspath("test_media")
scanner = FolderScanner(folder, recursive=True, detect_by_content=True)

def on_finished(items):
    print(f"Toplam taranan medya: {len(items)}")
    titles = [it.title for it in items]
    print("Bulunanlar:", titles)
    # Doğal sıralamayı doğrula: Bölüm 2, Bölüm 10'dan önce olmalı
    idx2 = next(i for i, t in enumerate(titles) if "Bölüm 2" in t)
    idx10 = next(i for i, t in enumerate(titles) if "Bölüm 10" in t)
    assert idx2 < idx10, f"Bölüm 2 ({idx2}) Bölüm 10'dan ({idx10}) önce olmalı!"
    # Yanlış uzantılı .dat dosyasının içerik analiziyle tanındığını doğrula
    assert any("yanlis_uzanti" in t for t in titles), "yanlis_uzanti.dat tanınmalıydı!"
    print("Klasör tarama ve doğal sıralama BAŞARILI!")
    app.quit()

scanner.scanFinished.connect(on_finished)
scanner.start()
app.exec()
