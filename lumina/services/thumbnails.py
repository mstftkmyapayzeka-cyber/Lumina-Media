"""Video küçük resim (thumbnail) üretim ve önbellekleme servisi (PyAV)."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from lumina.services.paths import cache_dir

log = logging.getLogger(__name__)

def generate_video_thumbnail(video_path: str, width: int = 256, height: int = 144) -> Optional[str]:
    """Videodan tek bir anahtar kare çıkartıp önbelleğe yazar ve yolunu döndürür."""
    p = Path(video_path)
    if not p.is_file():
        return None

    # Benzersiz önbellek dosya adı (dosya yolu ve son değiştirilme tarihi karması)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        mtime = 0
    cache_key = hashlib.md5(f"{p.resolve()}_{mtime}".encode("utf-8")).hexdigest()
    thumb_path = cache_dir("thumbnails") / f"{cache_key}.jpg"

    if thumb_path.exists():
        return str(thumb_path)

    try:
        import av
        with av.open(video_path) as container:
            v_streams = [s for s in container.streams if s.type == "video"]
            if not v_streams:
                return None
            stream = v_streams[0]

            # Başlangıçtan biraz sonraki (en az 1 sn veya %5) kareye atla
            target_sec = 2.0
            if container.duration:
                dur_sec = container.duration / 1000000.0
                target_sec = min(5.0, dur_sec * 0.1)

            target_pts = int(target_sec / stream.time_base)
            container.seek(target_pts, any_frame=False, backward=True, stream=stream)

            for frame in container.decode(stream):
                # RGB24 formatına ve istenen boyuta dönüştür
                img = frame.to_image()
                img.thumbnail((width, height))
                img.save(str(thumb_path), format="JPEG", quality=85)
                return str(thumb_path)

    except Exception as exc:
        log.debug("Thumbnail üretilemedi (%s): %s", video_path, exc)

    return None
