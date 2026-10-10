"""libVLC tabanlı oynatma motoru.

``PlayerEngine`` arayüzden tamamen bağımsızdır: yalnızca bir pencere tutamacı (HWND)
alır, Qt sinyalleri yayınlar ve metotlarla kontrol edilir.

İş parçacığı kuralı
-------------------
libVLC olay geri çağrıları VLC'nin kendi iş parçacıklarında çalışır. Bu geri
çağrılar içinde **asla** libVLC fonksiyonu çağrılmaz (kilitlenme riski); yalnızca
dahili ``_vlcEvent`` sinyali yayınlanır. Sinyal kuyruklu bağlantı ile ana iş
parçacığına taşınır ve orada işlenir.
"""
from __future__ import annotations

import enum
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

from lumina.core.formats import is_stream_url
from lumina.core.vlc_loader import load_vlc
from lumina.services.i18n import t
from lumina.services.settings import Settings

log = logging.getLogger(__name__)
vlc = load_vlc()


class PlaybackState(enum.Enum):
    IDLE = "idle"
    OPENING = "opening"
    BUFFERING = "buffering"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ENDED = "ended"
    ERROR = "error"


@dataclass(frozen=True)
class Track:
    id: int
    name: str


# Dahili olay kodları (VLC iş parçacığından ana iş parçacığına taşınır)
_EV_OPENING, _EV_BUFFERING, _EV_PLAYING, _EV_PAUSED, _EV_STOPPED = range(5)
_EV_ENDED, _EV_ERROR, _EV_LENGTH, _EV_VOUT, _EV_ES, _EV_SEEKABLE = range(5, 11)

MIN_RATE, MAX_RATE = 0.25, 4.0
MAX_VOLUME = 200


def _hw_args(mode: str) -> list[str]:
    """Donanım hızlandırma ayarını libVLC argümanlarına çevirir."""
    if mode == "none":
        return ["--avcodec-hw=none"]
    if mode == "d3d11va":
        return ["--avcodec-hw=d3d11va"]
    if mode == "dxva2":
        return ["--avcodec-hw=dxva2"]
    if mode == "nvdec":
        return ["--codec=nvdec,any", "--avcodec-hw=any"]
    return ["--avcodec-hw=any"]


class PlayerEngine(QObject):
    """libVLC MediaPlayer sarmalayıcısı."""

    stateChanged = Signal(object)            # PlaybackState
    positionChanged = Signal(int, int)       # zaman_ms, süre_ms
    lengthChanged = Signal(int)
    mediaOpened = Signal(str)                # kaynak (yol veya URL)
    mediaEnded = Signal()
    errorOccurred = Signal(str, str)         # kaynak, kullanıcıya gösterilecek mesaj
    volumeChanged = Signal(int, bool)        # ses (0..200), sessiz mi
    rateChanged = Signal(float)
    tracksChanged = Signal()
    videoOutputChanged = Signal(bool)        # video çıkışı var mı
    bufferingChanged = Signal(float)         # 0..100
    seekableChanged = Signal(bool)

    _vlcEvent = Signal(int, float)

    def __init__(self, settings: Settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._hwnd: int = 0
        self._instance: vlc.Instance | None = None
        self._player: vlc.MediaPlayer | None = None
        self._event_manager = None
        self._media: vlc.Media | None = None
        self._source: str = ""
        self._state = PlaybackState.IDLE
        self._length = 0
        self._last_time = -1
        self._has_video = False
        self._reached_playing = False
        self._pending_seek: int | None = None
        self._volume = max(0, min(MAX_VOLUME, int(settings.get("player.volume", 80))))
        self._muted = bool(settings.get("player.muted", False))
        self._rate = 1.0

        self._vlcEvent.connect(self._handle_vlc_event, Qt.ConnectionType.QueuedConnection)

        self._poll = QTimer(self)
        self._poll.setInterval(100)
        self._poll.timeout.connect(self._poll_position)

        self._create_backend()

    # ================================================================ yaşam döngüsü
    def _instance_args(self) -> list[str]:
        s = self._settings
        args = [
            "--ignore-config",            # kullanıcının VLC ayarları bizi etkilemesin
            "--no-video-title-show",
            "--no-sub-autodetect-file",   # altyazıyı biz buluyor ve kodlamasını düzeltiyoruz
            "--no-snapshot-preview",
            "--no-osd",
            "--no-stats",
            "--no-media-library",
            "--quiet",
            "--audio-time-stretch",       # hız değişiminde ses perdesi korunur
            f"--network-caching={int(s.get('player.network_caching', 1500))}",
            f"--file-caching={int(s.get('player.file_caching', 600))}",
        ]
        args += _hw_args(str(s.get("player.hw_decoding", "auto")))
        args += self._subtitle_style_args()
        return args

    def _subtitle_style_args(self) -> list[str]:
        s = self._settings
        args = [f"--freetype-font={s.get('subtitle.font', 'Segoe UI')}"]
        color = str(s.get("subtitle.color", "#FFFFFF")).lstrip("#")
        try:
            args.append(f"--freetype-color={int(color, 16)}")
        except ValueError:
            pass
        outline = {0: 0, 1: 2, 2: 4, 3: 6, 4: 6}.get(int(s.get("subtitle.outline", 2)), 4)
        args.append(f"--freetype-outline-thickness={outline}")
        size = int(s.get("subtitle.size", 0))
        if size:
            args.append(f"--freetype-rel-fontsize={size}")
        if s.get("subtitle.bold", False):
            args.append("--freetype-bold")
        if s.get("subtitle.background", False):
            args += ["--freetype-background-opacity=160", "--freetype-background-color=0"]
        margin = int(s.get("subtitle.position", 0))
        if margin:
            args.append(f"--sub-margin={margin}")
        return args

    def _create_backend(self) -> None:
        args = self._instance_args()
        log.info("libVLC instance argümanları: %s", " ".join(args))
        self._instance = vlc.Instance(args)
        if self._instance is None:
            raise RuntimeError("libVLC örneği oluşturulamadı")
        self._player = self._instance.media_player_new()
        self._player.video_set_mouse_input(False)
        self._player.video_set_key_input(False)
        if self._hwnd:
            self._player.set_hwnd(self._hwnd)
        self._attach_events()

    def _attach_events(self) -> None:
        assert self._player is not None
        em = self._player.event_manager()
        ET = vlc.EventType
        mapping = {
            ET.MediaPlayerOpening: _EV_OPENING,
            ET.MediaPlayerBuffering: _EV_BUFFERING,
            ET.MediaPlayerPlaying: _EV_PLAYING,
            ET.MediaPlayerPaused: _EV_PAUSED,
            ET.MediaPlayerStopped: _EV_STOPPED,
            ET.MediaPlayerEndReached: _EV_ENDED,
            ET.MediaPlayerEncounteredError: _EV_ERROR,
            ET.MediaPlayerLengthChanged: _EV_LENGTH,
            ET.MediaPlayerVout: _EV_VOUT,
            ET.MediaPlayerESAdded: _EV_ES,
            ET.MediaPlayerESDeleted: _EV_ES,
            ET.MediaPlayerSeekableChanged: _EV_SEEKABLE,
        }
        for vlc_type, code in mapping.items():
            em.event_attach(vlc_type, self._on_vlc_event, code)
        # Referansı tut: EventManager çöp toplanırsa ctypes geri çağrısı serbest kalır.
        self._event_manager = em
        self._event_types = list(mapping.keys())

    def _detach_events(self) -> None:
        if self._event_manager is None:
            return
        for et in self._event_types:
            try:
                self._event_manager.event_detach(et)
            except Exception:  # noqa: BLE001
                pass
        self._event_manager = None

    def _on_vlc_event(self, event, code: int) -> None:
        """VLC iş parçacığında çalışır — yalnızca sinyal yayınla."""
        value = 0.0
        try:
            if code == _EV_BUFFERING:
                value = float(event.u.new_cache)
            elif code == _EV_LENGTH:
                value = float(event.u.new_length)
            elif code == _EV_VOUT:
                value = float(event.u.new_count)
            elif code == _EV_SEEKABLE:
                value = float(event.u.new_seekable)
        except Exception:  # noqa: BLE001
            pass
        self._vlcEvent.emit(code, value)

    def attach_video_window(self, hwnd: int) -> None:
        """Videonun çizileceği native pencere tutamacını bağlar."""
        self._hwnd = int(hwnd)
        if self._player is not None:
            self._player.set_hwnd(self._hwnd)

    def rebuild(self) -> None:
        """Instance seviyesindeki ayarlar değişince motoru yeniden kurar.

        Çalan medya varsa aynı konumdan ve aynı duraklatma durumuyla sürdürülür.
        """
        source = self._source
        pos = self.time() if source else 0
        was_paused = self._state == PlaybackState.PAUSED
        self._teardown()
        self._create_backend()
        if source:
            self.open(source, start_ms=max(0, pos), paused=was_paused)

    def _teardown(self) -> None:
        self._poll.stop()
        self._detach_events()
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:  # noqa: BLE001
                pass
            self._player.release()
            self._player = None
        if self._media is not None:
            self._media.release()
            self._media = None
        if self._instance is not None:
            self._instance.release()
            self._instance = None

    def shutdown(self) -> None:
        """Uygulama kapanırken tüm libVLC kaynaklarını serbest bırakır."""
        self._teardown()
        self._source = ""

    # ================================================================ medya açma
    @staticmethod
    def _precheck_local(path: str) -> str | None:
        """Yerel dosya için açmadan önce anlaşılır hata mesajı üretir."""
        p = Path(path)
        if not p.exists():
            return t("error.file_missing", name=p.name)
        if p.is_dir():
            return t("error.is_directory", name=p.name)
        try:
            if p.stat().st_size == 0:
                return t("error.file_empty", name=p.name)
            with open(p, "rb") as f:
                f.read(1)
        except PermissionError:
            return t("error.file_permission", name=p.name)
        except OSError as exc:
            return t("error.file_unreadable", name=p.name, detail=str(exc))
        return None

    def open(self, source: str, start_ms: int = 0, paused: bool = False) -> bool:
        """Bir dosyayı veya akış URL'sini açar ve oynatmaya başlar.

        Dönüş: Açma isteği başarıyla verildiyse ``True``. Gerçek oynatma hataları
        ``errorOccurred`` sinyaliyle bildirilir.
        """
        assert self._instance is not None and self._player is not None
        stream = is_stream_url(source)
        if not stream:
            source = os.path.normpath(os.path.abspath(source))
            problem = self._precheck_local(source)
            if problem:
                self._player.stop()
                self._poll.stop()
                self._source = source
                self._set_state(PlaybackState.ERROR)
                self.errorOccurred.emit(source, problem)
                return False

        media = self._instance.media_new(source) if stream else self._instance.media_new_path(source)
        if media is None:
            self.errorOccurred.emit(source, t("error.cannot_open", name=os.path.basename(source)))
            return False
        if start_ms > 0:
            media.add_option(f":start-time={start_ms / 1000.0:.3f}")
        if paused:
            media.add_option(":start-paused")

        old = self._media
        self._media = media
        self._source = source
        self._length = 0
        self._last_time = -1
        self._has_video = False
        self._reached_playing = False
        self._pending_seek = None
        self._player.set_media(media)
        if old is not None:
            old.release()
        log.info("Açılıyor: %s (başlangıç=%d ms, duraklatılmış=%s)", source, start_ms, paused)
        self._set_state(PlaybackState.OPENING)
        if self._player.play() == -1:
            self._set_state(PlaybackState.ERROR)
            self.errorOccurred.emit(source, t("error.cannot_open", name=os.path.basename(source)))
            return False
        self.mediaOpened.emit(source)
        self._poll.start()
        return True

    # ================================================================ kontroller
    def play(self) -> None:
        if self._player is None or not self._source:
            return
        if self._state in (PlaybackState.ENDED, PlaybackState.STOPPED, PlaybackState.ERROR):
            self.open(self._source)
            return
        self._player.set_pause(0)
        self._poll.start()

    def pause(self) -> None:
        if self._player is not None and self._player.can_pause():
            self._player.set_pause(1)

    def toggle_pause(self) -> None:
        if self._state == PlaybackState.PLAYING:
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        if self._player is None:
            return
        self._player.stop()
        self._poll.stop()
        self._last_time = -1
        self.positionChanged.emit(0, self._length)

    def seek(self, ms: int) -> None:
        """Mutlak konuma (ms) atlar."""
        if self._player is None or not self._source:
            return
        ms = max(0, int(ms))
        if self._length > 0:
            ms = min(ms, max(0, self._length - 250))
        if not self._reached_playing:
            self._pending_seek = ms
            return
        if self._state == PlaybackState.ENDED:
            self.open(self._source, start_ms=ms)
            return
        if self._player.is_seekable():
            self._player.set_time(ms)
        elif self._length > 0:
            self._player.set_position(ms / self._length)
        self._last_time = ms
        self.positionChanged.emit(ms, self._length)

    def seek_relative(self, delta_ms: int) -> None:
        self.seek(self.time() + int(delta_ms))

    def set_position(self, fraction: float) -> None:
        if self._length > 0:
            self.seek(int(self._length * max(0.0, min(1.0, fraction))))

    def frame_step(self) -> None:
        """Bir sonraki kareye geçer (oynatma duraklatılır)."""
        if self._player is not None and self._has_video:
            self._player.next_frame()
            QTimer.singleShot(60, self._poll_position)

    # ---------------------------------------------------------------- ses
    def volume(self) -> int:
        return self._volume

    def is_muted(self) -> bool:
        return self._muted

    def set_volume(self, value: int) -> None:
        value = max(0, min(MAX_VOLUME, int(value)))
        changed = value != self._volume
        self._volume = value
        if value > 0 and self._muted:
            self._muted = False
            changed = True
        self._apply_volume()
        self._settings.set("player.volume", value)
        self._settings.set("player.muted", self._muted)
        if changed:
            self.volumeChanged.emit(self._volume, self._muted)

    def change_volume(self, delta: int) -> None:
        self.set_volume(self._volume + delta)

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        self._apply_volume()
        self._settings.set("player.muted", self._muted)
        self.volumeChanged.emit(self._volume, self._muted)

    def toggle_mute(self) -> None:
        self.set_muted(not self._muted)

    def _apply_volume(self) -> None:
        if self._player is None:
            return
        self._player.audio_set_volume(self._volume)
        self._player.audio_set_mute(self._muted)

    # ---------------------------------------------------------------- hız
    def rate(self) -> float:
        return self._rate

    def set_rate(self, rate: float) -> None:
        rate = round(max(MIN_RATE, min(MAX_RATE, float(rate))), 2)
        self._rate = rate
        if self._player is not None:
            self._player.set_rate(rate)
        self.rateChanged.emit(rate)

    # ---------------------------------------------------------------- izler
    @staticmethod
    def _decode(name) -> str:
        if isinstance(name, bytes):
            return name.decode("utf-8", errors="replace")
        return str(name)

    def _tracks(self, items) -> list[Track]:
        return [Track(int(i), self._decode(n)) for i, n in (items or [])]

    def audio_tracks(self) -> list[Track]:
        return self._tracks(self._player.audio_get_track_description()) if self._player else []

    def audio_track(self) -> int:
        return self._player.audio_get_track() if self._player else -1

    def set_audio_track(self, track_id: int) -> None:
        if self._player is not None:
            self._player.audio_set_track(int(track_id))
            self.tracksChanged.emit()

    def subtitle_tracks(self) -> list[Track]:
        return self._tracks(self._player.video_get_spu_description()) if self._player else []

    def subtitle_track(self) -> int:
        return self._player.video_get_spu() if self._player else -1

    def set_subtitle_track(self, track_id: int) -> None:
        if self._player is not None:
            self._player.video_set_spu(int(track_id))
            self.tracksChanged.emit()

    def add_subtitle_file(self, path: str, select: bool = True) -> bool:
        """Harici altyazı dosyasını (UTF-8 olmalı) oynatıcıya ekler."""
        if self._player is None:
            return False
        uri = "file:///" + quote(str(Path(path).resolve()).replace("\\", "/"), safe="/:")
        ok = self._player.add_slave(vlc.MediaSlaveType.subtitle, uri, bool(select)) == 0
        if ok:
            QTimer.singleShot(300, self.tracksChanged.emit)
        return ok

    # ---------------------------------------------------------------- sorgular
    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def source(self) -> str:
        return self._source

    def is_playing(self) -> bool:
        return self._state == PlaybackState.PLAYING

    def is_active(self) -> bool:
        """Yüklü ve durdurulmamış bir medya var mı?"""
        return self._state in (PlaybackState.OPENING, PlaybackState.BUFFERING,
                               PlaybackState.PLAYING, PlaybackState.PAUSED)

    def has_video(self) -> bool:
        return self._has_video

    def time(self) -> int:
        if self._player is None:
            return 0
        tm = self._player.get_time()
        return max(0, int(tm)) if tm is not None else 0

    def length(self) -> int:
        return self._length

    def is_seekable(self) -> bool:
        return bool(self._player and self._player.is_seekable())

    def video_size(self) -> tuple[int, int]:
        if self._player is None:
            return (0, 0)
        try:
            w, h = self._player.video_get_size(0)
            return int(w), int(h)
        except Exception:  # noqa: BLE001 - video yoksa python-vlc istisna fırlatır
            return (0, 0)

    def raw_player(self) -> "vlc.MediaPlayer | None":
        """Gelişmiş özellikler (Aşama 4) için alttaki libVLC oynatıcısı."""
        return self._player

    # ================================================================ olay işleme
    def _set_state(self, state: PlaybackState) -> None:
        if state != self._state:
            self._state = state
            self.stateChanged.emit(state)

    @Slot(int, float)
    def _handle_vlc_event(self, code: int, value: float) -> None:
        if self._player is None:
            return
        if code == _EV_OPENING:
            self._set_state(PlaybackState.OPENING)
        elif code == _EV_BUFFERING:
            self.bufferingChanged.emit(value)
        elif code == _EV_PLAYING:
            first = not self._reached_playing
            self._reached_playing = True
            if first:
                # Ses/hız ayarları yeni medya ile sıfırlanabildiği için yeniden uygula.
                self._apply_volume()
                if abs(self._rate - 1.0) > 1e-3:
                    self._player.set_rate(self._rate)
                if self._pending_seek is not None:
                    target, self._pending_seek = self._pending_seek, None
                    QTimer.singleShot(0, lambda: self.seek(target))
            self._set_state(PlaybackState.PLAYING)
            self._poll.start()
        elif code == _EV_PAUSED:
            if not self._reached_playing:
                # :start-paused ile açıldı: ilk kare gösterildi, motor hazır.
                self._reached_playing = True
                self._apply_volume()
            self._set_state(PlaybackState.PAUSED)
            self._poll_position()
        elif code == _EV_STOPPED:
            if self._state != PlaybackState.ERROR:
                self._set_state(PlaybackState.STOPPED)
            self._poll.stop()
        elif code == _EV_ENDED:
            self._poll.stop()
            if not self._reached_playing and self._length <= 0:
                # Hiç oynamadan bitti: içerik çözülemedi demektir.
                self._report_playback_error()
                return
            self._set_state(PlaybackState.ENDED)
            self.positionChanged.emit(self._length, self._length)
            self.mediaEnded.emit()
        elif code == _EV_ERROR:
            self._poll.stop()
            self._report_playback_error()
        elif code == _EV_LENGTH:
            self._length = max(0, int(value))
            self.lengthChanged.emit(self._length)
        elif code == _EV_VOUT:
            has = value > 0
            if has != self._has_video:
                self._has_video = has
                self.videoOutputChanged.emit(has)
        elif code == _EV_ES:
            self.tracksChanged.emit()
        elif code == _EV_SEEKABLE:
            self.seekableChanged.emit(value > 0)

    def _report_playback_error(self) -> None:
        src = self._source
        name = os.path.basename(src) if not is_stream_url(src) else src
        msg = t("error.stream_failed", url=src) if is_stream_url(src) else t("error.playback_failed", name=name)
        log.warning("Oynatma hatası: %s", src)
        self._set_state(PlaybackState.ERROR)
        self.errorOccurred.emit(src, msg)

    def _poll_position(self) -> None:
        if self._player is None:
            return
        tm = self.time()
        if self._length <= 0:
            ln = self._player.get_length()
            if ln and ln > 0:
                self._length = int(ln)
                self.lengthChanged.emit(self._length)
        if tm != self._last_time:
            self._last_time = tm
            self.positionChanged.emit(tm, self._length)
