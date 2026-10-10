"""Türkçe karakterli (CP1254) altyazı tespiti ve UTF-8 dönüşüm testi."""
import os
from pathlib import Path
from lumina.services.subtitles import find_subtitles_for_video, normalize_subtitle_to_utf8

video_p = os.path.abspath("test_media/Dizi Bölüm 1.mp4")
subs = find_subtitles_for_video(video_p)
print("Bulunan altyazılar:", subs)
assert len(subs) >= 1

best = subs[0]
utf8_path = normalize_subtitle_to_utf8(best)
print("Dönüştürülen altyazı:", utf8_path)

content = Path(utf8_path).read_text(encoding="utf-8")
print("İçerik önizleme:", repr(content[:80]))
assert "ğüşıöç" in content, "Türkçe karakterler korunmalıydı!"
print("Altyazı testi BAŞARILI!")
