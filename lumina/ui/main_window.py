"""Lumina Player Ana Penceresi — Modern Çerçevesiz Tasarım ve Eksiksiz libVLC Entegrasyonu."""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from lumina.core.media_item import MediaItem
from lumina.core.player import PlaybackState, PlayerEngine
from lumina.services.history import HistoryManager
from lumina.services.i18n import t
from lumina.services.paths import pictures_dir
from lumina.services.settings import Settings
from lumina.services.subtitles import find_subtitles_for_video, normalize_subtitle_to_utf8
from lumina.services.windows.power import WindowsPowerManager
from lumina.ui.audio_view import AudioView
from lumina.ui.control_bar import ControlBar
from lumina.ui.dialogs.equalizer_dialog import EqualizerDialog
from lumina.ui.dialogs.media_info_dialog import MediaInfoDialog
from lumina.ui.playlist_panel import PlaylistPanel
from lumina.ui.settings_dialog import SettingsDialog
from lumina.ui.theme import ACCENTS, theme
from lumina.ui.title_bar import TitleBar
from lumina.ui.video_widget import VideoWidget
from lumina.ui.welcome_view import WelcomeView

log = logging.getLogger(__name__)


def win11_polish(win: QWidget) -> None:
    """Windows 11: yuvarlak pencere köşeleri ve koyu sistem çerçevesi desteği."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = int(win.winId())
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), 4)  # DWMWA_WINDOW_CORNER_PREFERENCE = ROUND
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1 if theme.mode == "dark" else 0)), 4)
    except Exception:
        pass


class EdgeGrip(QWidget):
    """Çerçevesiz pencerede kenar/köşeden yeniden boyutlandırma tutamacı."""
    CURSORS = {
        Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
        Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
    }

    def __init__(self, edges: Qt.Edge, parent: QWidget) -> None:
        super().__init__(parent)
        self.edges = edges
        diag = (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
        back = (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge)
        if edges in diag:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges in back:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.setCursor(self.CURSORS.get(edges, Qt.CursorShape.ArrowCursor))

    def mousePressEvent(self, e) -> None:  # noqa: N802
        h = self.window().windowHandle()
        if e.button() == Qt.MouseButton.LeftButton and h is not None:
            h.startSystemResize(self.edges)


class MainWindow(QWidget):
    GRIP = 6

    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("Root")
        self.setWindowTitle(t("app.name"))
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.resize(1280, 760)
        self.setMinimumSize(880, 560)

        # Tema yapılandırması
        theme_mode = self.settings.get("ui.theme", "dark")
        accent = self.settings.get("ui.accent", "blue")
        theme.set_mode("dark" if theme_mode != "light" else "light")
        theme.set_accent(accent)

        # Temel Hizmetler
        self.history_mgr = HistoryManager()
        self.power_mgr = WindowsPowerManager()
        self.engine = PlayerEngine(self.settings, self)

        # Durum değişkenleri
        self._pos = 0
        self._dur = 0
        self._playing = False
        self._is_fullscreen = False
        self._is_pip = False

        self._init_ui()
        self._connect_signals()
        self._setup_shortcuts()

        # libVLC pencere yüzeyini bağla
        self.engine.attach_video_window(int(self.video_widget.winId()))

        # Windows 11 polish
        win11_polish(self)

    def _init_ui(self) -> None:
        self.title_bar = TitleBar(self)
        self.welcome_view = WelcomeView(self)
        self.video_widget = VideoWidget(self)
        self.audio_view = AudioView(self)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.welcome_view)   # 0
        self.stack.addWidget(self.video_widget)   # 1
        self.stack.addWidget(self.audio_view)     # 2

        self.playlist_panel = PlaylistPanel(self, opened=False)

        # Yüzen kontrol çubuğu
        self.control_bar = ControlBar(self)
        self.control_bar.attach_to(self.stack)
        self.control_bar.hide()

        # Ana Düzen
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.stack, 1)
        body.addWidget(self.playlist_panel)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.title_bar)
        root.addLayout(body, 1)

        # Kenar tutamaçları (Edge grips)
        self.grips = [
            EdgeGrip(e, self)
            for e in (
                Qt.Edge.LeftEdge,
                Qt.Edge.RightEdge,
                Qt.Edge.TopEdge,
                Qt.Edge.BottomEdge,
                Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
                Qt.Edge.RightEdge | Qt.Edge.TopEdge,
                Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
                Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
            )
        ]
        self._place_grips()

        # Başlangıçta Hoş Geldin ekranı
        self.stack.setCurrentWidget(self.welcome_view)

    # ── Pencere ve Tutamaç Konumlandırma ───────────────────────────────────────────
    def _place_grips(self) -> None:
        if not hasattr(self, "grips"):
            return
        g, w, h = self.GRIP, self.width(), self.height()
        L, R, T, B = Qt.Edge.LeftEdge, Qt.Edge.RightEdge, Qt.Edge.TopEdge, Qt.Edge.BottomEdge
        rects = {
            L: (0, g, g, h - 2 * g),
            R: (w - g, g, g, h - 2 * g),
            T: (g, 0, w - 2 * g, g),
            B: (g, h - g, w - 2 * g, g),
            L | T: (0, 0, g, g),
            R | T: (w - g, 0, g, g),
            L | B: (0, h - g, g, g),
            R | B: (w - g, h - g, g, g),
        }
        for grip in self.grips:
            grip.setGeometry(*rects[grip.edges])
            grip.raise_()
            grip.setVisible(not (self.isMaximized() or self.isFullScreen()))

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._place_grips()

    def changeEvent(self, e) -> None:  # noqa: N802
        super().changeEvent(e)
        self._place_grips()

    # ── Sinyal Bağlantıları ───────────────────────────────────────────────────────────
    def _connect_signals(self) -> None:
        # Başlık Çubuğu
        self.title_bar.openFileRequested.connect(self.open_file_dialog)
        self.title_bar.openFolderRequested.connect(self.open_folder_dialog)
        self.title_bar.openUrlRequested.connect(self.open_url_dialog)
        self.title_bar.settingsRequested.connect(self.show_settings)

        # Hoş Geldin Ekranı
        self.welcome_view.openFileRequested.connect(self.open_file_dialog)
        self.welcome_view.openFolderRequested.connect(self.open_folder_dialog)
        self.welcome_view.openUrlRequested.connect(self.open_url_dialog)
        self.welcome_view.pathsDropped.connect(self.handle_dropped_paths)

        # Kontrol Çubuğu
        b = self.control_bar
        b.playPauseClicked.connect(self.engine.toggle_pause)
        b.stopClicked.connect(self.stop)
        b.previousClicked.connect(self.play_previous)
        b.nextClicked.connect(self.play_next)
        b.skipRequested.connect(lambda delta_ms: self.engine.seek_relative(delta_ms))
        b.seekRequested.connect(self.engine.seek)
        b.volumeChanged.connect(self.engine.set_volume)
        b.mutedChanged.connect(self.engine.set_muted)
        b.speedChanged.connect(self.engine.set_rate)
        b.subtitleSelected.connect(self.engine.set_subtitle_track)
        b.subtitleFileRequested.connect(self._load_external_subtitle)
        b.audioTrackSelected.connect(self.engine.set_audio_track)
        b.screenshotClicked.connect(self.take_screenshot)
        b.pipClicked.connect(self.toggle_pip)
        b.playlistToggled.connect(self.set_playlist)
        b.fullscreenToggled.connect(self.set_fullscreen)
        b.visibilityChanged.connect(self._on_bar_visibility)

        # Çalma Listesi Paneli
        p = self.playlist_panel
        p.itemActivated.connect(self._on_playlist_item_activated)
        p.closeRequested.connect(lambda: self.set_playlist(False))
        p.openChanged.connect(b.set_playlist_checked)
        p.addFilesRequested.connect(self.open_file_dialog)
        p.addFolderRequested.connect(self.open_folder_dialog)
        p.pathsDropped.connect(self.handle_dropped_paths)
        p.cleared.connect(self.stop)

        # Oynatıcı Motoru (PlayerEngine)
        self.engine.stateChanged.connect(self._on_player_state_changed)
        self.engine.positionChanged.connect(self._on_player_position_changed)
        self.engine.mediaEnded.connect(self._on_media_ended)
        self.engine.errorOccurred.connect(self._on_player_error)

        # Video Yüzeyi
        self.video_widget.doubleClicked.connect(lambda: self.set_fullscreen(not self.isFullScreen()))
        self.video_widget.clicked.connect(self.engine.toggle_pause)
        self.video_widget.wheelScrolled.connect(lambda d: self.engine.change_volume(5 if d > 0 else -5))
        self.video_widget.filesDropped.connect(self.handle_dropped_paths)

    def _setup_shortcuts(self) -> None:
        def _sc(key: str, slot):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(slot)

        _sc("Space", self.engine.toggle_pause)
        _sc("Left", lambda: self.engine.seek_relative(-self.settings.get("player.seek_step_small", 5) * 1000))
        _sc("Right", lambda: self.engine.seek_relative(self.settings.get("player.seek_step_small", 5) * 1000))
        _sc("Shift+Left", lambda: self.engine.seek_relative(-self.settings.get("player.seek_step_large", 30) * 1000))
        _sc("Shift+Right", lambda: self.engine.seek_relative(self.settings.get("player.seek_step_large", 30) * 1000))
        _sc("Up", lambda: self.engine.change_volume(5))
        _sc("Down", lambda: self.engine.change_volume(-5))
        _sc("F", lambda: self.set_fullscreen(not self.isFullScreen()))
        _sc("M", self.engine.toggle_mute)
        _sc("S", self.take_screenshot)
        _sc("P", lambda: self.set_playlist(not self.playlist_panel.is_open()))
        _sc("N", self.play_next)
        _sc("B", self.play_previous)
        _sc("E", self.engine.frame_step)
        _sc("[", lambda: self.engine.set_rate(max(0.25, self.engine.rate() - 0.25)))
        _sc("]", lambda: self.engine.set_rate(min(4.0, self.engine.rate() + 0.25)))
        _sc("Ctrl+O", self.open_file_dialog)
        _sc("Ctrl+Shift+O", self.open_folder_dialog)
        _sc("Ctrl+U", self.open_url_dialog)
        _sc("Escape", self._on_escape_pressed)

    def _on_escape_pressed(self) -> None:
        if self.isFullScreen():
            self.set_fullscreen(False)
        elif self.playlist_panel.is_open():
            self.set_playlist(False)

    # ── Tam Ekran, Çalma Listesi ve Görünürlük ─────────────────────────────────────
    def set_fullscreen(self, on: bool) -> None:
        if on == self.isFullScreen():
            return
        self._is_fullscreen = on
        self.title_bar.setVisible(not on)
        if on:
            self.showFullScreen()
        else:
            self.showNormal()
        self.control_bar.set_fullscreen_checked(on)
        self._place_grips()

    def set_playlist(self, on: bool) -> None:
        self.playlist_panel.set_open(on)
        self.control_bar.set_playlist_checked(on)

    def _on_bar_visibility(self, shown: bool) -> None:
        if self.isFullScreen() or self._playing:
            self.stack.setCursor(Qt.CursorShape.ArrowCursor if shown else Qt.CursorShape.BlankCursor)

    def toggle_pip(self) -> None:
        self._is_pip = not self._is_pip
        flags = self.windowFlags()
        if self._is_pip:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    # ── Oynatma Akışı ─────────────────────────────────────────────────────────────
    def play_item(self, item: MediaItem) -> None:
        log.info("Medya başlatılıyor: %s (%s)", item.title, item.path)
        self.title_bar.set_media_title(item.title)

        start_ms = 0
        if self.settings.get("general.resume_playback", True):
            saved_pos = self.history_mgr.get_progress(item.path)
            if saved_pos and saved_pos > 5000:
                start_ms = saved_pos

        if item.kind == "audio":
            self.audio_view.set_metadata(item.title, "Bilinmeyen Sanatçı", item.ext)
            self.stack.setCurrentWidget(self.audio_view)
        else:
            self.stack.setCurrentWidget(self.video_widget)

        self.control_bar.attach_to(self.stack)
        self.control_bar.show()

        self.engine.open(item.path, start_ms=start_ms)

        # Otomatik altyazı yükle
        if item.kind == "video" and self.settings.get("subtitle.auto_load", True):
            subs = find_subtitles_for_video(item.path)
            if subs:
                best_sub = normalize_subtitle_to_utf8(subs[0])
                self.engine.add_subtitle_file(best_sub, select=True)

        # Altyazı ve ses izlerini güncelle
        QTimer.singleShot(500, self._sync_tracks_menu)

    def _on_playlist_item_activated(self, row: int, item: MediaItem) -> None:
        self.play_item(item)

    def play_next(self) -> None:
        nxt = self.playlist_panel.next_row()
        if nxt >= 0:
            self.playlist_panel.activate(nxt)
        else:
            self.stop()

    def play_previous(self) -> None:
        prv = self.playlist_panel.prev_row()
        if prv >= 0:
            self.playlist_panel.activate(prv)

    def stop(self) -> None:
        self.engine.stop()
        self.control_bar.set_playing(False)
        self.audio_view.set_playing(False)
        self.playlist_panel.set_playing(False)
        self.title_bar.set_media_title("")
        self.control_bar.hide()
        self.stack.setCurrentWidget(self.welcome_view)

    def _on_player_state_changed(self, state: PlaybackState) -> None:
        is_playing = (state == PlaybackState.PLAYING)
        self._playing = is_playing
        self.control_bar.set_playing(is_playing)
        self.audio_view.set_playing(is_playing)
        self.playlist_panel.set_playing(is_playing)

        if self.settings.get("player.prevent_sleep", True):
            self.power_mgr.prevent_sleep(is_playing)

        if is_playing:
            self._sync_tracks_menu()

    def _on_player_position_changed(self, pos_ms: int, dur_ms: int) -> None:
        self._pos = pos_ms
        self._dur = dur_ms
        self.control_bar.set_duration(dur_ms)
        self.control_bar.set_position(pos_ms)

        # Çalma listesi kartında izleme ilerlemesini güncelle
        row = self.playlist_panel.current_row()
        if row >= 0 and dur_ms > 0:
            self.playlist_panel.set_progress(row, pos_ms / dur_ms)
            cur = self.playlist_panel.current_item()
            if cur:
                self.history_mgr.save_progress(cur.path, pos_ms, dur_ms)

    def _on_media_ended(self) -> None:
        log.info("Mevcut medya sona erdi, sıradakine geçiliyor...")
        self.play_next()

    def _on_player_error(self, source: str, error_msg: str) -> None:
        log.warning("Oynatma hatası: %s - %s", source, error_msg)
        if self.settings.get("player.auto_skip_on_error", True) and len(self.playlist_panel.model.items) > 1:
            QTimer.singleShot(1000, self.play_next)
        else:
            QMessageBox.warning(self, t("error.title"), error_msg)

    def _sync_tracks_menu(self) -> None:
        # Altyazı izleri
        sub_tracks = self.engine.subtitle_tracks()
        cur_sub = self.engine.subtitle_track()
        sub_entries = [(tr.name, tr.id) if hasattr(tr, "name") else tr for tr in sub_tracks]
        self.control_bar.set_subtitle_tracks(sub_entries, cur_sub)

        # Ses izleri
        audio_tracks = self.engine.audio_tracks()
        cur_aud = self.engine.audio_track()
        audio_entries = [(tr.name, tr.id) if hasattr(tr, "name") else tr for tr in audio_tracks]
        self.control_bar.set_audio_tracks(audio_entries, cur_aud)

    def _load_external_subtitle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Altyazı Dosyası Seç",
            "",
            "Altyazılar (*.srt *.ass *.ssa *.vtt *.sub)",
        )
        if path:
            utf8_path = normalize_subtitle_to_utf8(path)
            self.engine.add_subtitle_file(utf8_path, select=True)
            self._sync_tracks_menu()

    def take_screenshot(self) -> None:
        raw = self.engine.raw_player()
        if not raw or not self.engine.has_video():
            return
        target_dir = Path(self.settings.get("video.screenshot_dir", str(pictures_dir())))
        target_dir.mkdir(parents=True, exist_ok=True)
        fname = f"Lumina_{int(time.time())}.png"
        target_file = target_dir / fname
        try:
            raw.video_take_snapshot(0, str(target_file), 0, 0)
            log.info("Ekran görüntüsü kaydedildi: %s", target_file)
        except Exception as exc:
            log.warning("Ekran görüntüsü alınamadı: %s", exc)

    # ── Dosya / Klasör Açma ve Sürükle-Bırak ────────────────────────────────────────
    def open_file_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            t("dialog.open_file"),
            "",
            "Tüm Medya Dosyaları (*.*)",
        )
        if files:
            self.handle_dropped_paths(files)

    def open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("menu.open_folder"))
        if folder:
            self.playlist_panel.load_folder(folder)
            self.set_playlist(True)
            self._ensure_started()

    def open_url_dialog(self) -> None:
        url, ok = QInputDialog.getText(self, t("dialog.open_url_title"), t("dialog.open_url_label"))
        if ok and url.strip():
            url = url.strip()
            item = MediaItem(url, url.rsplit("/", 1)[-1] or url, "URL", "video")
            self.playlist_panel.add_items([item])
            self._ensure_started()

    def handle_dropped_paths(self, paths: List[str]) -> None:
        local_files: list[str] = []
        for p in paths:
            norm = os.path.normpath(p)
            if os.path.isdir(norm):
                self.playlist_panel.load_folder(norm)
                self.set_playlist(True)
                self._ensure_started()
                return
            elif p.startswith(("http://", "https://", "rtsp://")):
                item = MediaItem(p, p.rsplit("/", 1)[-1] or p, "URL", "video")
                self.playlist_panel.add_items([item])
            else:
                local_files.append(norm)

        if local_files:
            self.playlist_panel.add_paths(local_files)
            if len(local_files) > 1:
                self.set_playlist(True)

        self._ensure_started()

    def _ensure_started(self) -> None:
        if self.playlist_panel.current_row() < 0 and self.playlist_panel.model.items:
            self.playlist_panel.activate(0)

    # ── Ayarlar ve Tema ───────────────────────────────────────────────────────────
    def show_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            theme_mode = self.settings.get("ui.theme", "dark")
            accent = self.settings.get("ui.accent", "blue")
            theme.set_mode("dark" if theme_mode != "light" else "light")
            theme.set_accent(accent)
            self.engine.rebuild()
            win11_polish(self)
