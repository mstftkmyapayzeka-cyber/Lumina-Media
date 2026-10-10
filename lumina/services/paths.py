"""Uygulama genelinde kullanılan dosya sistemi yolları."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from lumina import __app_id__


def is_frozen() -> bool:
    """PyInstaller ile paketlenmiş olarak mı çalışıyoruz?"""
    return bool(getattr(sys, "frozen", False))


def package_dir() -> Path:
    """`lumina` paketinin bulunduğu klasör (paketli modda _internal/lumina veya _MEIPASS/lumina)."""
    if is_frozen():
        mei = getattr(sys, "_MEIPASS", None)
        if mei:
            return Path(mei) / "lumina"
        return Path(sys.executable).resolve().parent / "_internal" / "lumina"
    return Path(__file__).resolve().parent.parent


def project_root() -> Path:
    """Geliştirme modunda depo kökü; paketli modda exe klasörü."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return package_dir().parent


def resource_path(*parts: str) -> Path:
    """resources/ altındaki bir dosyanın mutlak yolu."""
    return package_dir().joinpath("resources", *parts)


def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def app_data_dir() -> Path:
    """Kullanıcı ayarları ve veritabanı: %APPDATA%/LuminaPlayer."""
    base = os.environ.get("LUMINA_DATA_DIR") or os.environ.get("APPDATA") or str(Path.home())
    return _ensure(Path(base) / __app_id__)


def cache_dir(sub: str = "") -> Path:
    """Önbellek (thumbnail, dönüştürülmüş altyazı): %LOCALAPPDATA%/LuminaPlayer/cache."""
    base = os.environ.get("LUMINA_CACHE_DIR") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    root = Path(base) / __app_id__ / "cache"
    return _ensure(root / sub if sub else root)


def log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return _ensure(Path(base) / __app_id__ / "logs")


def pictures_dir() -> Path:
    """Ekran görüntüleri için varsayılan klasör."""
    return Path.home() / "Pictures" / "Lumina Player"
