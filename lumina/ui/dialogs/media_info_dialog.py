"""Medya Bilgileri İletişim Kutusu (Codec, Çözünürlük, Bitrate, Kanallar, Boyut)."""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lumina.services.metadata import MediaInfoData, get_media_metadata

class MediaInfoDialog(QDialog):
    def __init__(self, file_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Medya Bilgileri")
        self.setFixedSize(460, 380)

        info = get_media_metadata(file_path)
        self._init_ui(file_path, info)

    def _init_ui(self, path: str, info: Optional[MediaInfoData]) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # Genel Bilgiler Kutusu
        gen_box = QGroupBox("Genel Bilgiler")
        gen_grid = QGridLayout(gen_box)

        name = info.file_name if info else path
        size = info.file_size_formatted if info else "Bilinmiyor"
        fmt = info.format_name if info else "Bilinmiyor"

        gen_grid.addWidget(QLabel("Dosya Adı:"), 0, 0)
        lbl_name = QLabel(name)
        lbl_name.setWordWrap(True)
        gen_grid.addWidget(lbl_name, 0, 1)

        gen_grid.addWidget(QLabel("Dosya Boyutu:"), 1, 0)
        gen_grid.addWidget(QLabel(size), 1, 1)

        gen_grid.addWidget(QLabel("Biçim / Konteyner:"), 2, 0)
        gen_grid.addWidget(QLabel(fmt), 2, 1)

        layout.addWidget(gen_box)

        # Video Bilgileri Kutusu
        v_box = QGroupBox("Video Akışı")
        v_grid = QGridLayout(v_box)

        v_codec = info.video_codec if (info and info.video_codec) else "Yok / Ses Dosyası"
        v_res = f"{info.video_width} × {info.video_height}" if (info and info.video_width) else "-"
        v_fps = f"{info.video_fps:.2f} FPS" if (info and info.video_fps > 0) else "-"

        v_grid.addWidget(QLabel("Video Codec:"), 0, 0)
        v_grid.addWidget(QLabel(v_codec), 0, 1)

        v_grid.addWidget(QLabel("Çözünürlük:"), 1, 0)
        v_grid.addWidget(QLabel(v_res), 1, 1)

        v_grid.addWidget(QLabel("Kare Hızı:"), 2, 0)
        v_grid.addWidget(QLabel(v_fps), 2, 1)

        layout.addWidget(v_box)

        # Ses Bilgileri Kutusu
        a_box = QGroupBox("Ses Akışı")
        a_grid = QGridLayout(a_box)

        a_codec = info.audio_codec if (info and info.audio_codec) else "-"
        a_ch = f"{info.audio_channels} Kanal (Stereo/Mono)" if (info and info.audio_channels) else "-"
        a_sr = f"{info.audio_sample_rate} Hz" if (info and info.audio_sample_rate) else "-"

        a_grid.addWidget(QLabel("Ses Codec:"), 0, 0)
        a_grid.addWidget(QLabel(a_codec), 0, 1)

        a_grid.addWidget(QLabel("Kanallar:"), 1, 0)
        a_grid.addWidget(QLabel(a_ch), 1, 1)

        a_grid.addWidget(QLabel("Örnekleme Hızı:"), 2, 0)
        a_grid.addWidget(QLabel(a_sr), 2, 1)

        layout.addWidget(a_box)

        # Kapat Butonu
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, 0, Qt.AlignRight)
