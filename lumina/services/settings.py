"""JSON tabanlı, şemalı uygulama ayarları.

Ayarlar `%APPDATA%/LuminaPlayer/settings.json` dosyasında tutulur. Noktalı anahtarlar
(ör. ``"player.volume"``) ile okunur/yazılır. Yazma işlemleri kısa bir gecikmeyle
toplanıp atomik olarak (geçici dosya + yeniden adlandırma) diske yazılır.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from lumina.services.paths import app_data_dir, pictures_dir

log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "general": {
        "language": "tr",               # tr | en
        "single_instance": True,
        "resume_playback": True,        # kaldığı yerden devam
        "restore_session": True,        # son çalma listesini geri yükle
        "scan_subfolders": True,
        "recent_limit": 20,
        "detect_by_content": True,      # uzantısı bilinmeyen dosyalarda içerik analizi
    },
    "player": {
        "volume": 80,                   # 0..200
        "muted": False,
        "seek_step_small": 5,           # sn  (← / →)
        "seek_step_large": 30,          # sn  (Shift + ← / →)
        "seek_step_huge": 60,           # sn  (Ctrl + ← / →)
        "rate": 1.0,
        "hw_decoding": "auto",          # auto | d3d11va | dxva2 | nvdec | none
        "network_caching": 1500,        # ms
        "file_caching": 600,            # ms
        "play_mode": "sequential",      # sequential | shuffle | repeat_all | repeat_one | stop_after
        "end_action": "none",           # none | quit | sleep | shutdown
        "auto_skip_on_error": True,
        "prevent_sleep": True,
    },
    "audio": {
        "device": "",
        "delay_ms": 0,
        "normalize": False,
        "compressor": False,
        "stereo_mode": "stereo",        # stereo | reverse | left | right | dolby | mono
        "eq_enabled": False,
        "eq_preset": -1,
        "eq_preamp": 0.0,
        "eq_bands": [0.0] * 10,
    },
    "video": {
        "aspect": "default",
        "deinterlace": "off",
        "screenshot_dir": str(pictures_dir()),
        "screenshot_format": "png",     # png | jpg
    },
    "subtitle": {
        "auto_load": True,
        "font": "Segoe UI",
        "size": 0,                      # 0 = otomatik, aksi halde göreli boyut (VLC: 20 küçük .. 6 büyük)
        "color": "#FFFFFF",
        "outline": 2,                   # 0..4
        "background": False,
        "position": 0,                  # alt kenar boşluğu (px)
        "bold": False,
    },
    "ui": {
        "theme": "dark",                # dark | light | system
        "accent": "blue",               # blue | purple | red | green | orange
        "controls_autohide_ms": 3000,
        "playlist_visible": False,
        "playlist_width": 360,
        "window_geometry": "",
        "mica": False,
    },
    "shortcuts": {},                    # eylem -> tuş dizisi (boş = varsayılan)
    "recent": {"files": [], "folders": []},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Settings(QObject):
    """Uygulama ayarları. ``changed(key, value)`` sinyali her değişiklikte yayınlanır."""

    changed = Signal(str, object)

    def __init__(self, path: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._path = path or (app_data_dir() / "settings.json")
        self._data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self.save_now)
        self.load()

    # ------------------------------------------------------------------ G/Ç
    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = _deep_merge(DEFAULTS, raw)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Ayarlar okunamadı, varsayılanlar kullanılıyor: %s", exc)
            self._data = copy.deepcopy(DEFAULTS)

    def save_now(self) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)
        except OSError as exc:
            log.error("Ayarlar kaydedilemedi: %s", exc)

    # ------------------------------------------------------------- erişim
    def get(self, key: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return copy.deepcopy(node) if isinstance(node, (dict, list)) else node

    def set(self, key: str, value: Any) -> None:
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if node.get(parts[-1]) == value:
            return
        node[parts[-1]] = value
        self._save_timer.start()
        self.changed.emit(key, value)

    def default(self, key: str) -> Any:
        node: Any = DEFAULTS
        for part in key.split("."):
            node = node[part]
        return copy.deepcopy(node)

    def reset_section(self, section: str) -> None:
        self._data[section] = copy.deepcopy(DEFAULTS[section])
        self._save_timer.start()
        self.changed.emit(section, self._data[section])

    # ---------------------------------------------------- son açılanlar
    def add_recent(self, kind: str, path: str) -> None:
        """kind: 'files' | 'folders'. En yeni başta, tekrarsız, sınırlı."""
        key = f"recent.{kind}"
        items: list[str] = [p for p in self.get(key, []) if os.path.normcase(p) != os.path.normcase(path)]
        items.insert(0, path)
        self.set(key, items[: int(self.get("general.recent_limit", 20))])

    def clear_recent(self) -> None:
        self.set("recent.files", [])
        self.set("recent.folders", [])
