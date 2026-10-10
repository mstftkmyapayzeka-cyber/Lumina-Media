"""Doğrulama amaçlı sentetik test medyası üretir.

Kullanım:
    python tools/make_test_media.py [hedef_klasör]

Üretilenler (varsayılan: test_media/):
    - "Dizi Bölüm 1.mp4", "Dizi Bölüm 2.mp4", "Dizi Bölüm 10.mp4"  (doğal sıralama testi)
    - "Dizi Bölüm 1.srt"   Windows-1254 kodlamalı Türkçe altyazı (ğüşıöç)
    - "iki_ses_izi.mkv"    iki ses izli (farklı frekans) video
    - "muzik.mp3" / "muzik.flac"  ses dosyaları
    - "yanlis_uzanti.dat"  aslında MP4 olan dosya (içerik tespiti testi)
    - "bozuk.mp4"          rastgele bayt (hata yönetimi testi)
    - "alt/Alt Klasör Video.mp4"  alt klasör tarama testi
"""
from __future__ import annotations

import math
import os
import shutil
import sys
from fractions import Fraction
from pathlib import Path

import av
import numpy as np


def _pick_video_codec() -> str:
    for name in ("libx264", "h264_mf", "mpeg4"):
        try:
            av.codec.Codec(name, "w")
            return name
        except Exception:
            continue
    raise RuntimeError("Uygun video kodlayıcı bulunamadı")


def _frame_image(i: int, w: int, h: int, hue: float) -> np.ndarray:
    """Hareketli renk geçişli + sayaç çubuklu basit bir kare üretir."""
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    t = i / 25.0
    r = (0.5 + 0.5 * np.sin(2 * math.pi * (x + t * 0.2 + hue))) * 255
    g = (0.5 + 0.5 * np.sin(2 * math.pi * (y + t * 0.15 + hue + 0.33))) * 255
    b = (0.5 + 0.5 * np.sin(2 * math.pi * (x + y + t * 0.1 + hue + 0.66))) * 255
    img = np.stack(np.broadcast_arrays(r, g, b), axis=-1).astype(np.uint8)
    # Saniye göstergesi: üstte ilerleyen beyaz çubuk
    bar = int((i % 25) / 25 * w)
    img[10:30, :bar] = 255
    # Saniye sayısı kadar kare blok
    sec = i // 25
    for k in range(sec % 20):
        img[h - 40:h - 20, 20 + k * 30:40 + k * 30] = (255, 255, 255)
    return img


def make_video(path: Path, seconds: int = 12, w: int = 1280, h: int = 720,
               hue: float = 0.0, audio_tracks: tuple[float, ...] = (440.0,)) -> None:
    codec = _pick_video_codec()
    container = "matroska" if path.suffix == ".mkv" else None
    with av.open(str(path), "w", format=container) as out:
        vs = out.add_stream(codec, rate=25)
        vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p"
        if codec == "libx264":
            vs.options = {"preset": "ultrafast", "crf": "28", "g": "25"}
        else:
            vs.bit_rate = 2_000_000
            vs.gop_size = 25
        a_streams = []
        for idx, freq in enumerate(audio_tracks):
            a = out.add_stream("aac", rate=48000)
            a.layout = "stereo"
            a.metadata["language"] = ["tur", "eng", "ger"][idx % 3]
            a.metadata["title"] = f"Ses {idx + 1} ({int(freq)} Hz)"
            a_streams.append((a, freq))

        total = seconds * 25
        for i in range(total):
            frame = av.VideoFrame.from_ndarray(_frame_image(i, w, h, hue), format="rgb24")
            for pkt in vs.encode(frame):
                out.mux(pkt)
        for pkt in vs.encode():
            out.mux(pkt)

        for a, freq in a_streams:
            sr, n = 48000, 1024
            pts = 0
            total_samples = seconds * sr
            while pts < total_samples:
                t = (np.arange(n) + pts) / sr
                tone = (0.2 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
                data = np.vstack([tone, tone])
                af = av.AudioFrame.from_ndarray(data, format="fltp", layout="stereo")
                af.sample_rate = sr
                af.pts = pts
                af.time_base = Fraction(1, sr)
                for pkt in a.encode(af):
                    out.mux(pkt)
                pts += n
            for pkt in a.encode():
                out.mux(pkt)


def make_audio(path: Path, seconds: int = 20) -> None:
    codec = {"mp3": "libmp3lame", ".mp3": "libmp3lame", ".flac": "flac"}[path.suffix]
    try:
        av.codec.Codec(codec, "w")
    except Exception:
        print(f"  ! {codec} yok, {path.name} atlandı")
        return
    with av.open(str(path), "w") as out:
        a = out.add_stream(codec, rate=44100)
        a.layout = "stereo"
        out.metadata["title"] = "Test Melodisi"
        out.metadata["artist"] = "Lumina"
        out.metadata["album"] = "Test Albümü"
        sr, n = 44100, 1152
        fmt = a.codec_context.format.name
        pts = 0
        notes = [261.6, 329.6, 392.0, 523.3, 392.0, 329.6]
        while pts < seconds * sr:
            t = (np.arange(n) + pts) / sr
            note = notes[int(pts / sr * 2) % len(notes)]
            env = 0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t)
            sig = (0.3 * env * (np.sin(2 * np.pi * note * t) + 0.3 * np.sin(2 * np.pi * note * 2 * t)))
            if fmt.startswith("s16"):
                arr = (sig * 32767).astype(np.int16)
                data = np.vstack([arr, arr]) if fmt.endswith("p") else np.column_stack([arr, arr]).reshape(1, -1)
            elif fmt.startswith("s32"):
                arr = (sig * 2147483647).astype(np.int32)
                data = np.vstack([arr, arr]) if fmt.endswith("p") else np.column_stack([arr, arr]).reshape(1, -1)
            else:
                arr = sig.astype(np.float32)
                data = np.vstack([arr, arr]) if fmt.endswith("p") else np.column_stack([arr, arr]).reshape(1, -1)
            af = av.AudioFrame.from_ndarray(data, format=fmt, layout="stereo")
            af.sample_rate = sr
            af.pts = pts
            af.time_base = Fraction(1, sr)
            for pkt in a.encode(af):
                out.mux(pkt)
            pts += n
        for pkt in a.encode():
            out.mux(pkt)


SRT_TR = """1
00:00:01,000 --> 00:00:04,000
Merhaba! Türkçe karakter testi: ğüşıöç ĞÜŞİÖÇ

2
00:00:05,000 --> 00:00:08,000
Işık, gölge, çiçek, şeker, üzüm, öğretmen

3
00:00:09,000 --> 00:00:11,500
<i>İtalik satır</i> — son altyazı
"""


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "test_media"
    root.mkdir(parents=True, exist_ok=True)
    (root / "alt").mkdir(exist_ok=True)
    print(f"Hedef: {root}  (video kodlayıcı: {_pick_video_codec()})")

    jobs = [
        (root / "Dizi Bölüm 1.mp4", dict(hue=0.0)),
        (root / "Dizi Bölüm 2.mp4", dict(hue=0.3, seconds=8)),
        (root / "Dizi Bölüm 10.mp4", dict(hue=0.6, seconds=8)),
        (root / "iki_ses_izi.mkv", dict(hue=0.15, audio_tracks=(440.0, 880.0))),
        (root / "alt" / "Alt Klasör Video.mp4", dict(hue=0.8, seconds=6, w=854, h=480)),
        (root / "dikey_4k_test.mp4", dict(hue=0.45, seconds=5, w=3840, h=2160)),
    ]
    for path, kw in jobs:
        print(f"  + {path.name}")
        make_video(path, **kw)

    for p in (root / "muzik.mp3", root / "muzik.flac"):
        print(f"  + {p.name}")
        make_audio(p)

    (root / "Dizi Bölüm 1.srt").write_bytes(SRT_TR.encode("cp1254"))
    print("  + Dizi Bölüm 1.srt (cp1254)")
    shutil.copyfile(root / "Dizi Bölüm 2.mp4", root / "yanlis_uzanti.dat")
    print("  + yanlis_uzanti.dat")
    (root / "bozuk.mp4").write_bytes(os.urandom(256 * 1024))
    print("  + bozuk.mp4")
    print("Tamam.")


if __name__ == "__main__":
    main()
