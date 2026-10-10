"""M3U / M3U8 ve Lumina JSON çalma listesi dışa/içe aktarma modülü."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from lumina.core.media_item import MediaItem

def export_m3u(items: List[MediaItem], dest_path: str) -> None:
    lines = ["#EXTM3U\n"]
    for item in items:
        dur_sec = max(-1, item.duration_ms // 1000)
        lines.append(f"#EXTINF:{dur_sec},{item.title}\n")
        lines.append(f"{item.path}\n")

    Path(dest_path).write_text("".join(lines), encoding="utf-8")

def import_m3u(file_path: str) -> List[MediaItem]:
    items: List[MediaItem] = []
    p = Path(file_path)
    if not p.is_file():
        return items

    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    base_dir = p.parent

    cur_title = ""
    cur_dur_ms = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            # Ör: #EXTINF:120,Sanatçı - Parça Adı
            parts = line[8:].split(",", 1)
            try:
                cur_dur_ms = int(float(parts[0])) * 1000
            except ValueError:
                cur_dur_ms = 0
            if len(parts) > 1:
                cur_title = parts[1].strip()
        elif not line.startswith("#"):
            target_path = line
            if not os.path.isabs(target_path) and not target_path.startswith(("http://", "https://", "rtsp://")):
                target_path = str((base_dir / target_path).resolve())

            item = MediaItem(path=target_path, title=cur_title, duration_ms=cur_dur_ms)
            items.append(item)
            cur_title = ""
            cur_dur_ms = 0

    return items

def export_json(items: List[MediaItem], dest_path: str) -> None:
    data = [item.to_dict() for item in items]
    Path(dest_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def import_json(file_path: str) -> List[MediaItem]:
    p = Path(file_path)
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [MediaItem.from_dict(d) for d in raw if isinstance(d, dict)]
    except Exception:
        pass
    return []
