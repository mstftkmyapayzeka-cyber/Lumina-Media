"""libVLC çalışma zamanını bulur ve python-vlc'yi güvenle yükler.

Arama sırası:
    1. ``LUMINA_VLC_DIR`` ortam değişkeni
    2. Paketli uygulama: ``<exe>/vlc`` veya ``_MEIPASS/vlc``
    3. Geliştirme: ``<depo>/vendor/vlc`` (tools/fetch_vlc.ps1 ile hazırlanır)
    4. Sistemde kurulu 64-bit VLC (kayıt defteri / Program Files)

``import vlc`` ifadesi uygulamada yalnızca bu modül üzerinden yapılmalıdır; çünkü
python-vlc DLL yolunu içe aktarma anında belirler.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from types import ModuleType

from lumina.services.paths import is_frozen, project_root

log = logging.getLogger(__name__)

_vlc: ModuleType | None = None
_vlc_dir: Path | None = None
_dll_handles: list = []


class VlcNotFoundError(RuntimeError):
    """libVLC bulunamadı veya yüklenemedi."""


def _is_valid(d: Path) -> bool:
    return (d / "libvlc.dll").is_file() and (d / "libvlccore.dll").is_file() and (d / "plugins").is_dir()


def _registry_dirs() -> list[Path]:
    out: list[Path] = []
    try:
        import winreg
        for sub in (r"SOFTWARE\VideoLAN\VLC", r"SOFTWARE\WOW6432Node\VideoLAN\VLC"):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as k:
                    val, _ = winreg.QueryValueEx(k, "InstallDir")
                    out.append(Path(val))
            except OSError:
                continue
    except ImportError:
        pass
    return out


def candidate_dirs() -> list[Path]:
    c: list[Path] = []
    env = os.environ.get("LUMINA_VLC_DIR")
    if env:
        c.append(Path(env))
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        c.append(exe_dir / "_internal" / "vlc")
        c.append(exe_dir / "vlc")
        mei = getattr(sys, "_MEIPASS", None)
        if mei:
            c.append(Path(mei) / "vlc")
    c.append(project_root() / "vendor" / "vlc")
    c.extend(_registry_dirs())
    pf = os.environ.get("ProgramFiles")
    if pf:
        c.append(Path(pf) / "VideoLAN" / "VLC")
    return c


def find_vlc_dir() -> Path | None:
    for d in candidate_dirs():
        if _is_valid(d):
            return d.resolve()
    return None


def load_vlc() -> ModuleType:
    """python-vlc modülünü paketli libVLC ile yükler ve döndürür."""
    global _vlc, _vlc_dir
    if _vlc is not None:
        return _vlc
    d = find_vlc_dir()
    if d is None:
        raise VlcNotFoundError(
            "libVLC bulunamadı. Geliştirme için 'tools/fetch_vlc.ps1' betiğini çalıştırın."
        )
    os.environ["PYTHON_VLC_LIB_PATH"] = str(d / "libvlc.dll")
    os.environ["PYTHON_VLC_MODULE_PATH"] = str(d / "plugins")
    os.environ["VLC_PLUGIN_PATH"] = str(d / "plugins")
    if hasattr(os, "add_dll_directory"):
        _dll_handles.append(os.add_dll_directory(str(d)))
    try:
        import vlc  # noqa: PLC0415 - yolu ayarladıktan sonra bilinçli geç içe aktarma
    except (OSError, ImportError, AttributeError) as exc:
        raise VlcNotFoundError(f"libVLC yüklenemedi ({d}): {exc}") from exc
    if getattr(vlc, "dll", None) is None:
        raise VlcNotFoundError(f"libVLC yüklenemedi: {d}")
    _vlc, _vlc_dir = vlc, d
    log.info("libVLC %s yüklendi: %s", vlc.libvlc_get_version().decode(errors="replace"), d)
    return vlc


def vlc_dir() -> Path | None:
    return _vlc_dir


def vlc_version() -> str:
    if _vlc is None:
        return "?"
    return _vlc.libvlc_get_version().decode(errors="replace")
