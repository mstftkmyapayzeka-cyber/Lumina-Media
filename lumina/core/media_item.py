"""Çalma listesi ve kütüphane için Medya Öğesi veri yapısı."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lumina.core.formats import classify, display_name, is_stream_url


@dataclass
class MediaItem:
    path: str
    title: str = ""
    ext: str = ""
    kind: str = ""             # "video" | "audio"
    duration: int = 0          # saniye cinsinden
    duration_ms: int = 0       # milisaniye cinsinden
    resolution: str = ""       # "4K", "1080p", "720p" vb.
    width: int = 0
    height: int = 0
    size: int = 0
    mtime: float = 0.0
    progress: float = 0.0      # 0..1 izleme oranı
    progress_ms: int = 0       # ms cinsinden
    is_watched: bool = False
    thumbnail_path: Optional[str] = None
    extra_metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not is_stream_url(self.path):
            try:
                self.path = os.path.normpath(os.path.abspath(self.path))
            except Exception:
                pass
            if (self.size == 0 or self.mtime == 0.0) and os.path.exists(self.path):
                try:
                    st = os.stat(self.path)
                    self.size = st.st_size
                    self.mtime = st.st_mtime
                except OSError:
                    pass

        if not self.ext:
            self.ext = os.path.splitext(self.path)[1].upper().lstrip(".")

        if not self.title:
            self.title = display_name(self.path)

        if not self.kind and not is_stream_url(self.path):
            self.kind = classify(self.path) or "video"
        elif not self.kind:
            self.kind = "video"

        # Süre senkronizasyonu
        if self.duration > 0 and self.duration_ms == 0:
            self.duration_ms = self.duration * 1000
        elif self.duration_ms > 0 and self.duration == 0:
            self.duration = self.duration_ms // 1000

        # Çözünürlük etiketi
        if not self.resolution:
            self.resolution = self.resolution_label

        # İlerleme senkronizasyonu
        if self.progress > 0 and self.progress_ms == 0 and self.duration_ms > 0:
            self.progress_ms = int(self.progress * self.duration_ms)
        elif self.progress_ms > 0 and self.duration_ms > 0 and self.progress == 0.0:
            self.progress = min(1.0, max(0.0, self.progress_ms / self.duration_ms))

    @classmethod
    def from_path(cls, path: str, **kw) -> "MediaItem":
        p = Path(path)
        try:
            st = p.stat()
            size, mtime = st.st_size, st.st_mtime
        except OSError:
            size, mtime = 0, 0.0
        ext = p.suffix.lower()
        kind = "audio" if ext in (".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".aiff", ".alac") else "video"
        return cls(str(p), title=p.stem, ext=ext.lstrip(".").upper(), kind=kind, size=size, mtime=mtime, **kw)

    @property
    def resolution_label(self) -> str:
        if self.kind == "audio":
            return ""
        if self.resolution:
            return self.resolution
        if self.height >= 2160 or self.width >= 3840:
            return "4K"
        if self.height >= 1440 or self.width >= 2560:
            return "2K"
        if self.height >= 1080 or self.width >= 1920:
            return "1080p"
        if self.height >= 720 or self.width >= 1280:
            return "720p"
        if self.height >= 480:
            return "480p"
        if self.height > 0:
            return f"{self.height}p"
        return ""

    @property
    def type_line(self) -> str:
        parts: list[str] = []
        if self.kind == "audio":
            parts.append("Ses")
        else:
            parts.append("Video")
        if self.ext:
            parts.append(self.ext)
        if self.resolution:
            parts.append(self.resolution)
        return " • ".join(parts)

    @property
    def duration_formatted(self) -> str:
        sec = self.duration if self.duration > 0 else (self.duration_ms // 1000)
        if sec <= 0:
            return "--:--"
        hours = sec // 3600
        minutes = (sec % 3600) // 60
        seconds = sec % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "title": self.title,
            "ext": self.ext,
            "duration": self.duration,
            "duration_ms": self.duration_ms,
            "width": self.width,
            "height": self.height,
            "kind": self.kind,
            "progress": self.progress,
            "progress_ms": self.progress_ms,
            "is_watched": self.is_watched,
            "thumbnail_path": self.thumbnail_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MediaItem":
        return cls(
            path=data.get("path", ""),
            title=data.get("title", ""),
            ext=data.get("ext", ""),
            duration=data.get("duration", 0),
            duration_ms=data.get("duration_ms", 0),
            width=data.get("width", 0),
            height=data.get("height", 0),
            kind=data.get("kind", "video"),
            progress=data.get("progress", 0.0),
            progress_ms=data.get("progress_ms", 0),
            is_watched=data.get("is_watched", False),
            thumbnail_path=data.get("thumbnail_path"),
        )
