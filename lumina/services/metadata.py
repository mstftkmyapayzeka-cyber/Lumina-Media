"""Medya meta veri çıkarım servisi (pymediainfo ve PyAV)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

@dataclass
class MediaInfoData:
    file_name: str
    file_size_formatted: str
    duration_ms: int
    format_name: str
    video_codec: str = ""
    video_width: int = 0
    video_height: int = 0
    video_fps: float = 0.0
    video_bitrate: int = 0
    audio_codec: str = ""
    audio_channels: int = 0
    audio_sample_rate: int = 0
    audio_bitrate: int = 0

def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def get_media_metadata(file_path: str) -> Optional[MediaInfoData]:
    p = Path(file_path)
    if not p.is_file():
        return None

    size_bytes = p.stat().st_size
    info = MediaInfoData(
        file_name=p.name,
        file_size_formatted=format_file_size(size_bytes),
        duration_ms=0,
        format_name=p.suffix.lstrip(".").upper(),
    )

    # 1. Öncelik: pymediainfo
    try:
        from pymediainfo import MediaInfo
        mi = MediaInfo.parse(file_path)
        for track in mi.tracks:
            if track.track_type == "General":
                info.duration_ms = int(float(track.duration or 0))
                info.format_name = track.format or info.format_name
            elif track.track_type == "Video" and not info.video_codec:
                info.video_codec = track.format or track.codec_id or ""
                info.video_width = int(track.width or 0)
                info.video_height = int(track.height or 0)
                info.video_fps = float(track.frame_rate or 0)
                info.video_bitrate = int(track.bit_rate or 0)
            elif track.track_type == "Audio" and not info.audio_codec:
                info.audio_codec = track.format or ""
                info.audio_channels = int(track.channel_s or 0)
                info.audio_sample_rate = int(track.sampling_rate or 0)
                info.audio_bitrate = int(track.bit_rate or 0)
        return info
    except Exception as exc:
        log.debug("pymediainfo ile okunamadı, av ile deneniyor: %s", exc)

    # 2. Öncelik: PyAV
    try:
        import av
        with av.open(file_path) as container:
            info.duration_ms = int((container.duration or 0) / 1000)
            for stream in container.streams:
                if stream.type == "video" and not info.video_codec:
                    info.video_codec = stream.codec_context.name
                    info.video_width = stream.codec_context.width
                    info.video_height = stream.codec_context.height
                    info.video_fps = float(stream.rate) if stream.rate else 0.0
                elif stream.type == "audio" and not info.audio_codec:
                    info.audio_codec = stream.codec_context.name
                    info.audio_channels = stream.codec_context.channels
                    info.audio_sample_rate = stream.codec_context.sample_rate
        return info
    except Exception as exc:
        log.warning("Meta veri okunamadı: %s", exc)

    return info
