"""Günlük (log) kurulumu ve yakalanmamış hata yönetimi."""
from __future__ import annotations

import logging
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from typing import Callable

from lumina.services.paths import is_frozen, log_dir

_LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)s] %(threadName)s %(name)s: %(message)s"
_crash_handler: Callable[[str], None] | None = None


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Dönen dosya günlüğünü (%LOCALAPPDATA%/LuminaPlayer/logs/lumina.log) kurar."""
    root = logging.getLogger()
    if getattr(root, "_lumina_configured", False):
        return logging.getLogger("lumina")
    root.setLevel(level)
    fmt = logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    fh = RotatingFileHandler(log_dir() / "lumina.log", maxBytes=2 * 1024 * 1024,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    if not is_frozen() and sys.stderr is not None:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        root.addHandler(sh)

    root._lumina_configured = True  # type: ignore[attr-defined]
    return logging.getLogger("lumina")


def log_file_path() -> str:
    return str(log_dir() / "lumina.log")


def set_crash_handler(handler: Callable[[str], None] | None) -> None:
    """Yakalanmamış hatada (ana iş parçacığında) çağrılacak arayüz geri çağrısı."""
    global _crash_handler
    _crash_handler = handler


def _report(exc_type, exc, tb, where: str) -> None:
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    logging.getLogger("lumina.crash").critical("Yakalanmamış hata (%s):\n%s", where, text)
    if _crash_handler is not None:
        try:
            _crash_handler(text)
        except Exception:  # noqa: BLE001 - çökme bildiriminin kendisi çökmesin
            logging.getLogger("lumina.crash").exception("Çökme bildirimi gösterilemedi")


def install_exception_hooks() -> None:
    """sys.excepthook ve threading.excepthook'u günlüğe yazacak şekilde ayarlar.

    Qt slotlarında oluşan Python hataları sys.excepthook'a düşer; varsayılan
    davranış (PySide6) uygulamayı sonlandırmak değildir, biz de günlüğe yazıp
    kullanıcıyı bilgilendiririz.
    """
    def _hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        _report(exc_type, exc, tb, "ana")

    def _thread_hook(args: threading.ExceptHookArgs):
        _report(args.exc_type, args.exc_value, args.exc_traceback,
                f"thread:{args.thread.name if args.thread else '?'}")

    sys.excepthook = _hook
    threading.excepthook = _thread_hook
