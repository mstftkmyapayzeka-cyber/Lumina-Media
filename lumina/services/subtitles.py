"""Altyazı otomatik bulma, Türkçe karakter kodlama düzeltme (Windows-1254/UTF-8) ve yükleme."""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import charset_normalizer

from lumina.core.formats import SUBTITLE_EXTENSIONS
from lumina.services.paths import cache_dir

log = logging.getLogger(__name__)

def find_subtitles_for_video(video_path: str) -> list[str]:
    """Aynı dizinde video ile aynı adlı veya dil kodlu harici altyazıları bulur."""
    p = Path(video_path)
    if not p.is_file():
        return []

    parent = p.parent
    stem = p.stem.lower()
    found: list[str] = []

    try:
        for f in parent.iterdir():
            if f.is_file() and f.suffix.lower() in SUBTITLE_EXTENSIONS:
                f_stem = f.stem.lower()
                # Tam eşleşme veya videoadı.tr.srt, videoadı.en.srt gibi
                if f_stem == stem or f_stem.startswith(stem):
                    found.append(str(f.resolve()))
    except OSError as exc:
        log.warning("Altyazı taranırken hata: %s", exc)

    return found

def normalize_subtitle_to_utf8(sub_path: str) -> str:
    """Altyazı dosyasının kodlamasını tespit eder (Windows-1254, ISO-8859-9, UTF-8).
    
    Türkçe karakter bozulmasını önlemek için içeriği UTF-8'e çevirip önbelleğe yazar
    ve bu yeni dosyanın yolunu döndürür.
    """
    p = Path(sub_path)
    if not p.is_file():
        return sub_path

    try:
        raw_bytes = p.read_bytes()
    except OSError:
        return sub_path

    # 1. Önce doğrudan UTF-8 dene
    try:
        text = raw_bytes.decode("utf-8")
        return sub_path  # Zaten geçerli UTF-8
    except UnicodeDecodeError:
        pass

    # 2. Türkçe Windows-1254 / ISO-8859-9 kontrolü
    tr_chars = set("ğüşıöçĞÜŞİÖÇ")
    try:
        candidate_tr = raw_bytes.decode("cp1254")
        if any(c in candidate_tr for c in tr_chars):
            text = candidate_tr
            encoding = "cp1254"
        else:
            raise ValueError()
    except Exception:
        # 3. charset-normalizer genel tespiti
        matches = charset_normalizer.from_bytes(raw_bytes)
        best = matches.best()
        encoding = best.encoding if best else "cp1254"
        try:
            text = raw_bytes.decode(encoding, errors="replace")
        except Exception:
            text = raw_bytes.decode("cp1254", errors="replace")

    # Önbellek klasörüne UTF-8 olarak yaz
    dest_dir = cache_dir("subtitles")
    dest_path = dest_dir / f"{p.stem}_utf8{p.suffix}"
    try:
        dest_path.write_text(text, encoding="utf-8")
        log.info("Altyazı UTF-8'e dönüştürüldü (%s -> utf-8): %s", encoding, dest_path)
        return str(dest_path)
    except OSError:
        return sub_path
