"""10 Bantlı Ekolayzer ve Video Renk Ayarları İletişim Kutusu."""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lumina.core.player import PlayerEngine

EQ_FREQUENCIES = ["60 Hz", "170 Hz", "310 Hz", "600 Hz", "1 kHz", "3 kHz", "6 kHz", "12 kHz", "14 kHz", "16 kHz"]

EQ_PRESETS = {
    "Düz (Flat)": [0.0] * 10,
    "Pop": [-1.5, 0.0, 2.0, 3.5, 3.0, 1.0, -1.0, -1.5, -1.5, -1.0],
    "Rock": [4.0, 3.0, -1.0, -2.5, -0.5, 2.5, 4.0, 5.0, 5.0, 5.0],
    "Klasik": [4.5, 3.5, 3.0, 2.5, -1.5, -1.5, 0.0, 2.5, 3.5, 3.5],
    "Bas Artırma": [7.0, 5.5, 4.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "Tiz Artırma": [0.0, 0.0, 0.0, 0.0, 0.0, 1.5, 3.5, 6.0, 7.5, 8.0],
    "Vokal": [-2.0, -1.0, 0.0, 2.5, 4.0, 4.0, 2.5, 1.0, 0.0, -1.5],
}

class EqualizerDialog(QDialog):
    def __init__(self, player_engine: PlayerEngine, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.engine = player_engine
        self.setWindowTitle("Ses ve Görüntü Efektleri")
        self.setFixedSize(540, 420)

        self._band_sliders: List[QSlider] = []
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # 1. SEKME: Ses Ekolayzerı
        eq_tab = QWidget()
        eq_layout = QVBoxLayout(eq_tab)

        # Üst Satır: Aktif Kutusu ve Hazır Ayarlar
        top_row = QHBoxLayout()
        self.chk_enable_eq = QCheckBox("Ekolayzerı Etkinleştir")
        self.chk_enable_eq.toggled.connect(self._on_eq_toggled)
        top_row.addWidget(self.chk_enable_eq)

        top_row.addStretch(1)
        top_row.addWidget(QLabel("Hazır Ayar:"))
        self.combo_presets = QComboBox()
        self.combo_presets.addItems(list(EQ_PRESETS.keys()))
        self.combo_presets.currentTextChanged.connect(self._on_preset_changed)
        top_row.addWidget(self.combo_presets)
        eq_layout.addLayout(top_row)

        # 10 Bant Sürgüleri (Dikey)
        bands_box = QGroupBox("Frekans Bantları (-20 dB … +20 dB)")
        bands_layout = QHBoxLayout(bands_box)
        bands_layout.setSpacing(12)

        for i, freq in enumerate(EQ_FREQUENCIES):
            col = QVBoxLayout()
            col.setAlignment(Qt.AlignCenter)

            val_lbl = QLabel("0 dB")
            val_lbl.setStyleSheet("font-size: 10px; color: #9CA3AF;")
            val_lbl.setAlignment(Qt.AlignCenter)

            slider = QSlider(Qt.Vertical)
            slider.setRange(-20, 20)
            slider.setValue(0)
            slider.setFixedHeight(160)
            slider.valueChanged.connect(lambda val, idx=i, lbl=val_lbl: self._on_band_changed(idx, val, lbl))

            freq_lbl = QLabel(freq)
            freq_lbl.setStyleSheet("font-size: 9px; color: #64748B;")
            freq_lbl.setAlignment(Qt.AlignCenter)

            col.addWidget(val_lbl)
            col.addWidget(slider)
            col.addWidget(freq_lbl)
            bands_layout.addLayout(col)
            self._band_sliders.append(slider)

        eq_layout.addWidget(bands_box)
        tabs.addTab(eq_tab, "Ses Ekolayzerı")

        # 2. SEKME: Video Renk / Görüntü Ayarları
        video_tab = QWidget()
        video_layout = QVBoxLayout(video_tab)

        grid = QGridLayout()
        grid.setSpacing(14)

        # Parlaklık, Kontrast, Doygunluk, Gama
        self.slider_bright = self._create_video_slider("Parlaklık", 0, 200, 100, grid, 0, self._apply_video_adjust)
        self.slider_contrast = self._create_video_slider("Kontrast", 0, 200, 100, grid, 1, self._apply_video_adjust)
        self.slider_sat = self._create_video_slider("Doygunluk", 0, 300, 100, grid, 2, self._apply_video_adjust)
        self.slider_gamma = self._create_video_slider("Gama", 10, 300, 100, grid, 3, self._apply_video_adjust)

        video_layout.addLayout(grid)
        video_layout.addStretch(1)

        btn_reset_video = QPushButton("Renk Ayarlarını Sıfırla")
        btn_reset_video.clicked.connect(self._reset_video_adjust)
        video_layout.addWidget(btn_reset_video, 0, Qt.AlignRight)

        tabs.addTab(video_tab, "Video Ayarları")

        main_layout.addWidget(tabs)

        # Kapat Butonu
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.accept)
        main_layout.addWidget(btn_close, 0, Qt.AlignRight)

    def _create_video_slider(self, label: str, min_v: int, max_v: int, def_v: int, grid: QGridLayout, row: int, slot) -> QSlider:
        lbl = QLabel(label)
        val_lbl = QLabel(f"{def_v}%")
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(def_v)
        slider.valueChanged.connect(lambda v: (val_lbl.setText(f"{v}%"), slot()))

        grid.addWidget(lbl, row, 0)
        grid.addWidget(slider, row, 1)
        grid.addWidget(val_lbl, row, 2)
        return slider

    def _on_eq_toggled(self, checked: bool) -> None:
        raw = self.engine.raw_player()
        if raw:
            try:
                import vlc
                if checked:
                    eq = vlc.libvlc_audio_equalizer_new()
                    for i, s in enumerate(self._band_sliders):
                        vlc.libvlc_audio_equalizer_set_amp_at_index(eq, float(s.value()), i)
                    raw.set_equalizer(eq)
                else:
                    raw.set_equalizer(None)
            except Exception:
                pass

    def _on_preset_changed(self, name: str) -> None:
        values = EQ_PRESETS.get(name, [0.0] * 10)
        for i, val in enumerate(values):
            if i < len(self._band_sliders):
                self._band_sliders[i].setValue(int(val))

    def _on_band_changed(self, idx: int, val: int, label: QLabel) -> None:
        label.setText(f"{val:+d} dB")
        if self.chk_enable_eq.isChecked():
            self._on_eq_toggled(True)

    def _apply_video_adjust(self) -> None:
        raw = self.engine.raw_player()
        if not raw:
            return
        try:
            raw.video_set_adjust_int(1, 1)  # Enable adjust
            raw.video_set_adjust_float(3, self.slider_bright.value() / 100.0)    # Brightness
            raw.video_set_adjust_float(2, self.slider_contrast.value() / 100.0)  # Contrast
            raw.video_set_adjust_float(4, self.slider_sat.value() / 100.0)       # Saturation
            raw.video_set_adjust_float(5, self.slider_gamma.value() / 100.0)     # Gamma
        except Exception:
            pass

    def _reset_video_adjust(self) -> None:
        self.slider_bright.setValue(100)
        self.slider_contrast.setValue(100)
        self.slider_sat.setValue(100)
        self.slider_gamma.setValue(100)
        self._apply_video_adjust()
