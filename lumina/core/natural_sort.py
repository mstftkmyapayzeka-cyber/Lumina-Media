"""Doğal sıralama (Natural sort) algoritması: 'Bölüm 2', 'Bölüm 10'dan önce gelsin."""
from __future__ import annotations

import re
from typing import Any, List

_REGEX_CHUNKS = re.compile(r"(\d+|\D+)")

# Türkçe harf dönüşümleri (küçük harfe çevirirken 'I' -> 'ı', 'İ' -> 'i')
_TR_MAP = str.maketrans("IİĞÜŞÖÇ", "ıiğüşöç")

def _turkish_lower(text: str) -> str:
    return text.translate(_TR_MAP).lower()

def natural_sort_key(value: Any) -> List[Any]:
    """Metinleri ve sayıları doğru ayıran sıralama anahtarı döndürür."""
    s = str(value)
    s = _turkish_lower(s)
    chunks = _REGEX_CHUNKS.findall(s)
    key: List[Any] = []
    for chunk in chunks:
        if chunk.isdigit():
            key.append(int(chunk))
        else:
            key.append(chunk)
    return key
