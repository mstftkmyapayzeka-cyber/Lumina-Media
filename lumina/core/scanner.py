"""Klasör tarama iş parçacığı (QThread) - Arayüzü dondurmadan binlerce dosyayı tarar."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List
from PySide6.QtCore import QThread, Signal

from lumina.core.formats import classify, ext_of, MEDIA_EXTENSIONS
from lumina.core.media_item import MediaItem
from lumina.core.natural_sort import natural_sort_key

class FolderScanner(QThread):
    progress = Signal(int, int)       # bulunan_adet, taranan_klasör_sayısı
    batchDiscovered = Signal(list)    # bulunan MediaItem listesi (parti halinde)
    scanFinished = Signal(list)       # tüm bulunan MediaItem listesi

    def __init__(
        self,
        folder_path: str,
        recursive: bool = True,
        detect_by_content: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.folder_path = folder_path
        self.recursive = recursive
        self.detect_by_content = detect_by_content
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        all_items: List[MediaItem] = []
        batch: List[MediaItem] = []
        dirs_scanned = 0

        root_p = Path(self.folder_path)
        if not root_p.is_dir():
            self.scanFinished.emit([])
            return

        for current_root, dirs, files in os.walk(self.folder_path):
            if self._is_cancelled:
                break

            dirs_scanned += 1
            if not self.recursive:
                dirs.clear()  # Alt klasörlere inme

            for f in files:
                if self._is_cancelled:
                    break

                full_path = os.path.join(current_root, f)
                ext = ext_of(full_path)

                kind = None
                if ext in MEDIA_EXTENSIONS:
                    kind = classify(full_path, detect_by_content=False)
                elif self.detect_by_content:
                    kind = classify(full_path, detect_by_content=True)

                if kind in ("video", "audio"):
                    item = MediaItem(path=full_path, kind=kind)
                    batch.append(item)
                    all_items.append(item)

                    if len(batch) >= 50:
                        self.batchDiscovered.emit(list(batch))
                        self.progress.emit(len(all_items), dirs_scanned)
                        batch.clear()

        if batch:
            self.batchDiscovered.emit(list(batch))

        # Bulunan tüm listeyi ada göre doğal sıralamaya sok
        all_items.sort(key=lambda x: natural_sort_key(x.title))
        self.scanFinished.emit(all_items)
