"""Vektör SVG simgeleri sağlayıcısı (Lucide/Fluent tarzı 24x24 vektörler)."""
from __future__ import annotations

from typing import Dict
from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# 24x24 viewBox standart Lucide/Fluent tarzı simge SVG yolları
SVG_PATHS: Dict[str, str] = {
    "play": '<polygon points="5 3 19 12 5 21 5 3" fill="currentColor"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1" fill="currentColor"/><rect x="14" y="4" width="4" height="16" rx="1" fill="currentColor"/>',
    "stop": '<rect x="4" y="4" width="16" height="16" rx="2" fill="currentColor"/>',
    "prev": '<polygon points="19 20 9 12 19 4 19 20" fill="currentColor"/><line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "next": '<polygon points="5 4 15 12 5 20 5 4" fill="currentColor"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "seek_back": '<path d="M11 17l-5-5 5-5M18 17l-5-5 5-5" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "seek_fwd": '<path d="M13 17l5-5-5-5M6 17l5-5-5-5" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
    "volume_high": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
    "volume_low": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
    "volume_mute": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor"/><line x1="23" y1="9" x2="17" y2="15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="17" y1="9" x2="23" y2="15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "fullscreen": '<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
    "fullscreen_exit": '<path d="M4 14h6m0 0v6m0-6L3 21m17-11h-6m0 0V4m0 6l7-7M14 10h6m-6 0V4m0 6l7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
    "playlist": '<line x1="8" y1="6" x2="21" y2="6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="8" y1="12" x2="21" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="8" y1="18" x2="21" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="3" cy="6" r="1.5" fill="currentColor"/><circle cx="3" cy="12" r="1.5" fill="currentColor"/><circle cx="3" cy="18" r="1.5" fill="currentColor"/>',
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" fill="none"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="2" fill="none"/><polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="2" fill="none"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
    "settings": '<circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2" fill="none"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" stroke="currentColor" stroke-width="2" fill="none"/>',
    "camera": '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="12" cy="13" r="4" stroke="currentColor" stroke-width="2" fill="none"/>',
    "subtitle": '<rect x="2" y="4" width="20" height="16" rx="2" stroke="currentColor" stroke-width="2" fill="none"/><line x1="6" y1="14" x2="10" y2="14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="14" y1="14" x2="18" y2="14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="10" x2="18" y2="10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "audio": '<path d="M9 18V5l12-2v13" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><circle cx="6" cy="18" r="3" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="18" cy="16" r="3" stroke="currentColor" stroke-width="2" fill="none"/>',
    "info": '<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none"/><line x1="12" y1="16" x2="12" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="12" y1="8" x2="12.01" y2="8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "shuffle": '<polyline points="16 3 21 3 21 8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><line x1="4" y1="20" x2="21" y2="3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><polyline points="21 16 21 21 16 21" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><line x1="15" y1="15" x2="21" y2="21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="4" y1="4" x2="9" y2="9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "repeat": '<polyline points="17 1 21 5 17 9" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M3 11V9a4 4 0 0 1 4-4h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><polyline points="7 23 3 19 7 15" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M21 13v2a4 4 0 0 1-4 4H3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
    "repeat_one": '<polyline points="17 1 21 5 17 9" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M3 11V9a4 4 0 0 1 4-4h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><polyline points="7 23 3 19 7 15" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M21 13v2a4 4 0 0 1-4 4H3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><text x="12" y="15" font-size="8" font-weight="bold" fill="currentColor" text-anchor="middle">1</text>',
    "pip": '<rect x="2" y="4" width="20" height="16" rx="2" stroke="currentColor" stroke-width="2" fill="none"/><rect x="12" y="11" width="8" height="7" rx="1" fill="currentColor"/>',
    "close": '<line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "minimize": '<line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "maximize": '<rect x="4" y="4" width="16" height="16" rx="2" stroke="currentColor" stroke-width="2" fill="none"/>',
    "restore": '<rect x="7" y="7" width="13" height="13" rx="1.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M4 17V5a1 1 0 0 1 1-1h12" stroke="currentColor" stroke-width="2" fill="none"/>',
    "search": '<circle cx="11" cy="11" r="8" stroke="currentColor" stroke-width="2" fill="none"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    "trash": '<polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="2" fill="none"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="2" fill="none"/>',
    "check": '<polyline points="20 6 9 17 4 12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
}

_icon_cache: Dict[str, QIcon] = {}

def get_svg_icon(name: str, color: str = "#F3F4F6", size: int = 24) -> QIcon:
    cache_key = f"{name}_{color}_{size}"
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    body = SVG_PATHS.get(name, SVG_PATHS["file"])
    svg_data = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" color="{color}">
    {body}
</svg>"""

    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    icon = QIcon(pixmap)
    _icon_cache[cache_key] = icon
    return icon
