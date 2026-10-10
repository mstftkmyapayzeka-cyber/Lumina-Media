"""Basit JSON tabanlı çeviri (i18n) altyapısı.

Çeviriler ``resources/i18n/<dil>.json`` dosyalarında düz anahtar/değer olarak tutulur.
Kullanım::

    from lumina.services.i18n import t
    t("menu.open_file")                 # "Dosya Aç"
    t("error.file_missing", path=p)     # biçimlendirmeli
"""
from __future__ import annotations

import json
import logging

from lumina.services.paths import resource_path

log = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {"tr": "Türkçe", "en": "English"}
_current: dict[str, str] = {}
_fallback: dict[str, str] = {}
_lang = "tr"


def _load(lang: str) -> dict[str, str]:
    path = resource_path("i18n", f"{lang}.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.error("Çeviri dosyası yüklenemedi (%s): %s", path, exc)
        return {}


def set_language(lang: str) -> None:
    """Etkin dili ayarlar. Bilinmeyen anahtarlar Türkçe'ye, o da yoksa anahtarın kendisine düşer."""
    global _current, _fallback, _lang
    _lang = lang if lang in SUPPORTED_LANGUAGES else "tr"
    _fallback = _load("tr")
    _current = _fallback if _lang == "tr" else _load(_lang)


def language() -> str:
    return _lang


def t(key: str, **kwargs: object) -> str:
    if not _fallback:
        set_language(_lang)
    text = _current.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text
