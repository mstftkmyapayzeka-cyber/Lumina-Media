"""Kapsamlı Ayarlar Penceresi (Genel, Oynatma, Ses, Video, Altyazı, Arayüz, Hakkında)."""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from lumina import __app_name__, __version__
from lumina.services.settings import Settings

class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Lumina Player - Ayarlar")
        self.setFixedSize(620, 460)

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Sol Kategori Menüsü
        self.category_list = QListWidget()
        self.category_list.setFixedWidth(140)
        categories = ["Genel", "Oynatma", "Ses & Video", "Altyazı", "Arayüz", "Hakkında"]
        for cat in categories:
            self.category_list.addItem(cat)
        self.category_list.currentRowChanged.connect(self._on_category_changed)
        main_layout.addWidget(self.category_list)

        # Sağ Sayfalar Yığını
        self.pages_stack = QStackedWidget()

        self.pages_stack.addWidget(self._create_general_page())
        self.pages_stack.addWidget(self._create_playback_page())
        self.pages_stack.addWidget(self._create_audio_video_page())
        self.pages_stack.addWidget(self._create_subtitle_page())
        self.pages_stack.addWidget(self._create_ui_page())
        self.pages_stack.addWidget(self._create_about_page())

        main_layout.addWidget(self.pages_stack, 1)

        self.category_list.setCurrentRow(0)

    # ---------------------------------------------------------------- Sayfa Yapıcılar
    def _create_general_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        form = QFormLayout()
        self.chk_resume = QCheckBox("Kaldığın yerden devam et")
        self.chk_resume.setChecked(self.settings.get("general.resume_playback", True))
        self.chk_resume.toggled.connect(lambda v: self.settings.set("general.resume_playback", v))
        form.addRow(self.chk_resume)

        self.chk_restore = QCheckBox("Uygulama açılınca son listeyi geri yükle")
        self.chk_restore.setChecked(self.settings.get("general.restore_session", True))
        self.chk_restore.toggled.connect(lambda v: self.settings.set("general.restore_session", v))
        form.addRow(self.chk_restore)

        self.chk_subfolders = QCheckBox("Klasör açıldığında alt klasörleri de tara")
        self.chk_subfolders.setChecked(self.settings.get("general.scan_subfolders", True))
        self.chk_subfolders.toggled.connect(lambda v: self.settings.set("general.scan_subfolders", v))
        form.addRow(self.chk_subfolders)

        self.chk_content = QCheckBox("Uzantısı bilinmeyen dosyalarda içerik analizi yap")
        self.chk_content.setChecked(self.settings.get("general.detect_by_content", True))
        self.chk_content.toggled.connect(lambda v: self.settings.set("general.detect_by_content", v))
        form.addRow(self.chk_content)

        lay.addLayout(form)
        lay.addSpacing(16)

        # Windows Varsayılan Uygulama Yap Butonu
        btn_default = QPushButton("🎬 Videolar İçin Varsayılan Uygulama Yap")
        btn_default.setFixedHeight(34)
        btn_default.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_default.setStyleSheet(
            "QPushButton { background: #2563EB; color: white; font-weight: 600; border-radius: 6px; padding: 6px 14px; }"
            "QPushButton:hover { background: #3B82F6; }"
            "QPushButton:pressed { background: #1D4ED8; }"
        )
        btn_default.clicked.connect(self._make_default_app)
        lay.addWidget(btn_default)

        lbl_info = QLabel("Windows 10/11'de video dosyalarının (.mp4, .mkv, .avi vb.) çift tıklandığında doğrudan Lumina Player ile açılmasını sağlar.")
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        lay.addWidget(lbl_info)

        lay.addStretch(1)
        return w

    def _make_default_app(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        from lumina.services.windows.default_app import register_as_default_player, open_windows_default_apps_settings
        ok, msg = register_as_default_player(include_audio=True)
        if ok:
            QMessageBox.information(
                self,
                "Varsayılan Uygulama",
                "Lumina Player sistem kayıt defterine başarıyla işlendi!\n\n"
                "Açılan Windows Ayarları penceresinden veya dosyalara sağ tıklayıp "
                "'Birlikte Aç -> Başka bir uygulama seç -> Her zaman' diyerek Lumina Player'ı varsayılan olarak belirleyebilirsiniz."
            )
            open_windows_default_apps_settings()
        else:
            QMessageBox.warning(self, "Hata", f"Varsayılan uygulama kaydı yapılamadı:\n{msg}")

    def _create_playback_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        # Donanım Hızlandırma
        self.combo_hw = QComboBox()
        self.combo_hw.addItems(["auto", "d3d11va", "dxva2", "nvdec", "none"])
        self.combo_hw.setCurrentText(self.settings.get("player.hw_decoding", "auto"))
        self.combo_hw.currentTextChanged.connect(lambda v: self.settings.set("player.hw_decoding", v))
        form.addRow("Donanım Hızlandırma:", self.combo_hw)

        self.chk_prevent_sleep = QCheckBox("Video oynatılırken ekranın uyumasını engelle")
        self.chk_prevent_sleep.setChecked(self.settings.get("player.prevent_sleep", True))
        self.chk_prevent_sleep.toggled.connect(lambda v: self.settings.set("player.prevent_sleep", v))
        form.addRow(self.chk_prevent_sleep)

        self.chk_auto_skip = QCheckBox("Bozuk/okunamayan dosyada sıradakine geç")
        self.chk_auto_skip.setChecked(self.settings.get("player.auto_skip_on_error", True))
        self.chk_auto_skip.toggled.connect(lambda v: self.settings.set("player.auto_skip_on_error", v))
        form.addRow(self.chk_auto_skip)

        # Video Bitince Eylem
        self.combo_end_act = QComboBox()
        self.combo_end_act.addItems(["Hiçbir şey yapma", "Uygulamayı kapat", "Bilgisayarı uyut", "Bilgisayarı kapat"])
        form.addRow("Dosya / Liste bitince:", self.combo_end_act)

        lay.addLayout(form)
        lay.addStretch(1)
        return w

    def _create_audio_video_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        self.chk_normalize = QCheckBox("Ses normalizasyonu / ses dengeleme")
        self.chk_normalize.setChecked(self.settings.get("audio.normalize", False))
        self.chk_normalize.toggled.connect(lambda v: self.settings.set("audio.normalize", v))
        form.addRow(self.chk_normalize)

        # Ekran görüntüsü klasörü
        ss_row = QHBoxLayout()
        self.txt_ss_path = QLineEdit(self.settings.get("video.screenshot_dir", ""))
        btn_browse_ss = QPushButton("Seç…")
        btn_browse_ss.clicked.connect(self._browse_screenshot_dir)
        ss_row.addWidget(self.txt_ss_path, 1)
        ss_row.addWidget(btn_browse_ss)
        form.addRow("Ekran Görüntüsü Yolu:", ss_row)

        lay.addLayout(form)
        lay.addStretch(1)
        return w

    def _create_subtitle_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        self.chk_auto_sub = QCheckBox("Aynı dizindeki altyazıları otomatik yükle")
        self.chk_auto_sub.setChecked(self.settings.get("subtitle.auto_load", True))
        self.chk_auto_sub.toggled.connect(lambda v: self.settings.set("subtitle.auto_load", v))
        form.addRow(self.chk_auto_sub)

        self.txt_sub_font = QLineEdit(self.settings.get("subtitle.font", "Segoe UI"))
        self.txt_sub_font.textChanged.connect(lambda v: self.settings.set("subtitle.font", v))
        form.addRow("Altyazı Yazı Tipi:", self.txt_sub_font)

        self.combo_sub_color = QComboBox()
        self.combo_sub_color.addItems(["Beyaz (#FFFFFF)", "Sarı (#FDE047)", "Açık Mavi (#7DD3FC)"])
        form.addRow("Altyazı Rengi:", self.combo_sub_color)

        lay.addLayout(form)
        lay.addStretch(1)
        return w

    def _create_ui_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        # Tema
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Koyu (Dark)", "Açık (Light)"])
        self.combo_theme.setCurrentIndex(0 if self.settings.get("ui.theme", "dark") == "dark" else 1)
        self.combo_theme.currentIndexChanged.connect(
            lambda i: self.settings.set("ui.theme", "dark" if i == 0 else "light")
        )
        form.addRow("Arayüz Teması:", self.combo_theme)

        # Vurgu Rengi
        self.combo_accent = QComboBox()
        self.combo_accent.addItems(["Mavi (Blue)", "Mor (Purple)", "Kırmızı (Red)", "Yeşil (Green)", "Turuncu (Orange)"])
        acc_map = {"blue": 0, "purple": 1, "red": 2, "green": 3, "orange": 4}
        cur_acc = self.settings.get("ui.accent", "blue")
        self.combo_accent.setCurrentIndex(acc_map.get(cur_acc, 0))
        rev_acc = ["blue", "purple", "red", "green", "orange"]
        self.combo_accent.currentIndexChanged.connect(lambda i: self.settings.set("ui.accent", rev_acc[i]))
        form.addRow("Vurgu Rengi:", self.combo_accent)

        lay.addLayout(form)
        lay.addStretch(1)
        return w

    def _create_about_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)

        lbl_app = QLabel(f"{__app_name__} v{__version__}")
        lbl_app.setStyleSheet("font-size: 16px; font-weight: 700; color: #3B82F6;")
        lay.addWidget(lbl_app)

        lbl_desc = QLabel(
            "Windows 10/11 için geliştirilmiş modern, şık ve güçlü video ve medya oynatıcısı.\n"
            "Oynatma motoru: libVLC (VideoLAN LGPL 2.1+).\n\n"
            "Önemli Yasal ve Lisans Bildirimi:\n"
            "• Lumina Player, video ve ses çözücü motoru olarak libVLC kütüphanesini dinamik olarak kullanır (LGPL v2.1+).\n"
            "• DRM Uyarısı: Netflix, Spotify gibi ticari DRM (Widevine) ile korunan akışlar desteklenmez; yerel ve açık ortam dosyaları oynatılır."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #9CA3AF; line-height: 1.4;")
        lay.addWidget(lbl_desc)

        lay.addStretch(1)
        return w

    def _on_category_changed(self, row: int) -> None:
        self.pages_stack.setCurrentIndex(row)

    def _browse_screenshot_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Ekran Görüntüsü Klasörü Seç")
        if path:
            self.txt_ss_path.setText(path)
            self.settings.set("video.screenshot_dir", path)
