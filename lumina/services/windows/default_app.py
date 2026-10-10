"""Windows 10/11 dosya ilişkilendirmeleri ve Varsayılan Uygulama (Default App) entegrasyonu."""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import winreg
from typing import List, Tuple

log = logging.getLogger(__name__)

VIDEO_EXTENSIONS = [
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv",
    ".m4v", ".mpg", ".mpeg", ".ts", ".m2ts", ".3gp", ".vob", ".ogv"
]

AUDIO_EXTENSIONS = [
    ".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".opus", ".wma"
]


def get_lumina_executable() -> str:
    """Çalışan veya derlenmiş LuminaPlayer.exe yolunu bulur."""
    if getattr(sys, "frozen", False):
        return os.path.normpath(sys.executable)

    # Proje içindeki derlenmiş LuminaPlayer.exe varsa öncelikli olarak onu kullan
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    dist_exe = os.path.join(project_root, "dist", "LuminaPlayer", "LuminaPlayer.exe")
    if os.path.exists(dist_exe):
        return os.path.normpath(dist_exe)

    # Geliştirme ortamında pythonw.exe ile lumina çalıştırma komutu
    py_dir = os.path.dirname(sys.executable)
    pyw = os.path.join(py_dir, "pythonw.exe")
    if os.path.exists(pyw):
        return os.path.normpath(pyw)
    return os.path.normpath(sys.executable)


def register_as_default_player(include_audio: bool = False) -> Tuple[bool, str]:
    """Lumina Player'ı HKCU (Geçerli Kullanıcı) kayıt defterine video/ses oynatıcı olarak kaydeder."""
    try:
        exe_path = get_lumina_executable()
        prog_id = "LuminaPlayer.Video"
        app_name = "Lumina Player"

        if getattr(sys, "frozen", False) or exe_path.endswith("LuminaPlayer.exe"):
            open_cmd = f'"{exe_path}" "%1"'
            icon_str = f'"{exe_path}",0'
        else:
            # Geliştirme ortamı için python -m lumina
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            open_cmd = f'"{exe_path}" -m lumina "%1"'
            icon_str = f'"{exe_path}",0'

        # 1. HKCU\Software\Classes\LuminaPlayer.Video oluştur
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "Lumina Video Dosyası")
            winreg.SetValueEx(k, "FriendlyTypeName", 0, winreg.REG_SZ, "Lumina Video Dosyası")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\DefaultIcon") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, icon_str)

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, open_cmd)

        # 2. HKCU\Software\Classes\Applications\LuminaPlayer.exe
        app_key_path = r"Software\Classes\Applications\LuminaPlayer.exe"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_key_path) as k:
            winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, app_name)

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{app_key_path}\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, open_cmd)

        # 3. Dosya uzantılarını ilişkilendir
        extensions = list(VIDEO_EXTENSIONS)
        if include_audio:
            extensions.extend(AUDIO_EXTENSIONS)

        for ext in extensions:
            # OpenWithProgids
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}\OpenWithProgids") as k:
                winreg.SetValueEx(k, prog_id, 0, winreg.REG_NONE, b"")

            # Applications SupportedTypes
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{app_key_path}\SupportedTypes") as k:
                winreg.SetValueEx(k, ext, 0, winreg.REG_SZ, "")

        # 4. Windows Yetenekleri (Capabilities) Kaydı (Windows 10/11 Varsayılan Uygulamalar için)
        cap_path = r"Software\LuminaPlayer\Capabilities"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cap_path) as k:
            winreg.SetValueEx(k, "ApplicationDescription", 0, winreg.REG_SZ, "Modern ve güçlü Windows Medya Oynatıcısı")
            winreg.SetValueEx(k, "ApplicationName", 0, winreg.REG_SZ, app_name)

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{cap_path}\FileAssociations") as k:
            for ext in extensions:
                winreg.SetValueEx(k, ext, 0, winreg.REG_SZ, prog_id)

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\RegisteredApplications") as k:
            winreg.SetValueEx(k, "LuminaPlayer", 0, winreg.REG_SZ, cap_path)

        # 5. Windows Gezgini'ne ilişkilendirme değişikliğini bildir (SHCNE_ASSOCCHANGED = 0x08000000)
        try:
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass

        log.info("Lumina Player kayıt defterine başarıyla işlendi: %s", exe_path)
        return True, "Kayıt defteri ayarları başarıyla tamamlandı."

    except Exception as exc:
        log.exception("Varsayılan oynatıcı kaydı başarısız: %s", exc)
        return False, str(exc)


def open_windows_default_apps_settings() -> None:
    """Windows 10/11 Varsayılan Uygulamalar ayar sayfasını açar."""
    try:
        # Windows 10/11 URI protokolü
        os.system("start ms-settings:defaultapps")
    except Exception:
        try:
            subprocess.Popen(["control", "/name", "Microsoft.DefaultPrograms", "/page", "pageDefaultProgram"])
        except Exception as exc:
            log.warning("Varsayılan uygulamalar sayfası açılamadı: %s", exc)
