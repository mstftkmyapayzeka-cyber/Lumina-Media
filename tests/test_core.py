"""Lumina Player temel birim testleri (Playlist mantığı, Doğal Sıralama, Format tespiti, M3U)."""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from lumina.core.formats import classify, ext_of, is_video_ext, is_audio_ext
from lumina.core.m3u import export_json, export_m3u, import_json, import_m3u
from lumina.core.media_item import MediaItem
from lumina.core.natural_sort import natural_sort_key
from lumina.core.playlist import Playlist, PlayMode

def test_natural_sort():
    raw_list = ["Bölüm 10.mp4", "Bölüm 1.mp4", "Bölüm 2.mp4", "bölüm 3.mp4"]
    sorted_list = sorted(raw_list, key=natural_sort_key)
    assert sorted_list == ["Bölüm 1.mp4", "Bölüm 2.mp4", "bölüm 3.mp4", "Bölüm 10.mp4"]

def test_formats_classification():
    assert is_video_ext("film.mkv")
    assert is_video_ext("video.MP4")
    assert is_audio_ext("sarki.flac")
    assert is_audio_ext("ses.mp3")
    assert ext_of("test.tar.gz") == ".gz"

def test_playlist_modes_sequential():
    pl = Playlist()
    items = [MediaItem(path=f"file{i}.mp4", title=f"Video {i}") for i in range(3)]
    pl.add_items(items)
    assert pl.count() == 3

    pl.set_mode(PlayMode.SEQUENTIAL)
    pl.set_current_index(0)

    # 0 -> 1 -> 2 -> None
    assert pl.next_item().title == "Video 1"
    assert pl.next_item().title == "Video 2"
    assert pl.next_item() is None

def test_playlist_modes_repeat_all():
    pl = Playlist()
    items = [MediaItem(path=f"file{i}.mp4", title=f"Video {i}") for i in range(2)]
    pl.add_items(items)
    pl.set_mode(PlayMode.REPEAT_ALL)
    pl.set_current_index(1)

    # Sonuncu öğeden sonra başa sarmalı
    assert pl.next_item().title == "Video 0"

def test_playlist_modes_repeat_one():
    pl = Playlist()
    items = [MediaItem(path=f"file{i}.mp4", title=f"Video {i}") for i in range(2)]
    pl.add_items(items)
    pl.set_mode(PlayMode.REPEAT_ONE)
    pl.set_current_index(0)

    # Hep aynı öğeyi döndürmeli
    assert pl.next_item().title == "Video 0"
    assert pl.next_item().title == "Video 0"

def test_m3u_export_import(tmp_path: Path):
    items = [
        MediaItem(path=str(tmp_path / "v1.mp4"), title="Video 1", duration_ms=60000),
        MediaItem(path=str(tmp_path / "v2.mp4"), title="Video 2", duration_ms=120000),
    ]
    m3u_file = tmp_path / "test.m3u"
    export_m3u(items, str(m3u_file))
    assert m3u_file.exists()

    imported = import_m3u(str(m3u_file))
    assert len(imported) == 2
    assert imported[0].title == "Video 1"
    assert imported[0].duration_ms == 60000

def test_json_export_import(tmp_path: Path):
    items = [MediaItem(path="c:/test/film.mkv", title="Film", duration_ms=5000, width=1920, height=1080)]
    json_file = tmp_path / "test.json"
    export_json(items, str(json_file))

    imported = import_json(str(json_file))
    assert len(imported) == 1
    assert imported[0].title == "Film"
    assert imported[0].resolution_label == "1080p"
