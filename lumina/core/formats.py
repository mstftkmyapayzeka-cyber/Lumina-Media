"""Desteklenen biçimler ve içerik (magic byte) tabanlı medya tespiti."""
from __future__ import annotations

import os
from pathlib import Path

VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpg", ".mpeg", ".mpe", ".m1v", ".m2v",
    ".ts", ".m2ts", ".mts", ".m2t", ".vob", ".3gp", ".3g2", ".ogv", ".ogm", ".m4v", ".divx", ".xvid",
    ".rmvb", ".rm", ".asf", ".f4v", ".mxf", ".dv", ".evo", ".nsv", ".tod", ".trp", ".wtv", ".dvr-ms",
    ".y4m", ".h264", ".h265", ".hevc", ".264", ".265", ".ivf", ".amv", ".bik", ".mk3d",
})
AUDIO_EXTENSIONS: frozenset[str] = frozenset({
    ".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".oga", ".opus", ".wma", ".aiff", ".aif", ".aifc",
    ".ape", ".alac", ".mka", ".ac3", ".eac3", ".dts", ".dtshd", ".thd", ".mlp", ".mp2", ".mpa", ".m4b",
    ".wv", ".tta", ".mpc", ".spx", ".amr", ".au", ".snd", ".caf", ".mid", ".midi", ".mod", ".xm",
    ".it", ".s3m", ".w64", ".dsf", ".dff", ".tak", ".ra", ".voc", ".weba",
})
SUBTITLE_EXTENSIONS: frozenset[str] = frozenset({
    ".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx", ".smi", ".sami", ".txt", ".usf", ".mpl", ".jss",
    ".psb", ".rt", ".ttml", ".dfxp", ".stl", ".sbv",
})
PLAYLIST_EXTENSIONS: frozenset[str] = frozenset({".m3u", ".m3u8", ".pls", ".xspf", ".lumina.json"})

MEDIA_EXTENSIONS: frozenset[str] = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

# Kesinlikle medya olmayan yaygın uzantılar (içerik analizi bunlarda yapılmaz)
NON_MEDIA_EXTENSIONS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".svg", ".heic",
    ".nfo", ".txt", ".log", ".ini", ".json", ".xml", ".html", ".htm", ".css", ".js", ".py", ".md",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar", ".7z", ".tar", ".gz",
    ".exe", ".dll", ".msi", ".bat", ".cmd", ".ps1", ".lnk", ".url", ".db", ".sqlite", ".torrent",
    ".part", ".crdownload", ".tmp", ".sfv", ".md5", ".sha1", ".cue", ".iso", ".bin", ".img",
}) | SUBTITLE_EXTENSIONS | PLAYLIST_EXTENSIONS

STREAM_SCHEMES: tuple[str, ...] = (
    "http://", "https://", "rtsp://", "rtmp://", "rtp://", "udp://", "mms://", "mmsh://", "ftp://",
    "srt://", "smb://",
)


def ext_of(path: str | os.PathLike[str]) -> str:
    name = os.fspath(path).lower()
    if name.endswith(".lumina.json"):
        return ".lumina.json"
    return os.path.splitext(name)[1]


def is_stream_url(text: str) -> bool:
    return text.strip().lower().startswith(STREAM_SCHEMES)


def is_video_ext(path: str | os.PathLike[str]) -> bool:
    return ext_of(path) in VIDEO_EXTENSIONS


def is_audio_ext(path: str | os.PathLike[str]) -> bool:
    return ext_of(path) in AUDIO_EXTENSIONS


def is_subtitle_ext(path: str | os.PathLike[str]) -> bool:
    # .txt altyazı da olabilir ama otomatik olarak altyazı sayılmaz (yanlış pozitif riski)
    return ext_of(path) in (SUBTITLE_EXTENSIONS - {".txt"})


def is_playlist_ext(path: str | os.PathLike[str]) -> bool:
    return ext_of(path) in PLAYLIST_EXTENSIONS


def sniff_media_kind(path: str | os.PathLike[str]) -> str | None:
    """Dosyanın ilk baytlarına bakarak medya türünü tahmin eder.

    Dönüş: ``"video"``, ``"audio"`` veya ``None`` (medya değil / tanınmadı).
    Uzantısı yanlış veya olmayan dosyalar için kullanılır.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return None
    if len(head) < 12:
        return None

    # ISO BMFF (MP4/MOV/M4A/3GP): 4 bayt boyut + 'ftyp'
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"M4A ", b"M4B ", b"M4P ", b"F4A ", b"F4B "):
            return "audio"
        return "video"
    if head[4:8] in (b"moov", b"mdat", b"free", b"wide", b"skip"):
        return "video"
    # Matroska / WebM (EBML)
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "video"
    # RIFF: AVI / WAV
    if head[:4] == b"RIFF":
        kind = head[8:12]
        if kind in (b"AVI ", b"AVIX"):
            return "video"
        if kind in (b"WAVE", b"RMP3"):
            return "audio"
        return None
    # ASF / WMV / WMA
    if head[:16] == bytes.fromhex("3026B2758E66CF11A6D900AA0062CE6C"):
        return "video"
    # FLV
    if head[:3] == b"FLV":
        return "video"
    # RealMedia
    if head[:4] == b".RMF":
        return "video"
    # MPEG-PS / VOB
    if head[:4] == b"\x00\x00\x01\xba":
        return "video"
    # MPEG elementary video
    if head[:4] == b"\x00\x00\x01\xb3":
        return "video"
    # MPEG-TS (188 baytlık paketler, 0x47 senkron baytı) / M2TS (192 bayt)
    if len(head) >= 188 * 3 and head[0] == 0x47 and head[188] == 0x47 and head[376] == 0x47:
        return "video"
    if len(head) >= 192 * 3 and head[4] == 0x47 and head[196] == 0x47 and head[388] == 0x47:
        return "video"
    # Ogg: Theora ise video, değilse ses
    if head[:4] == b"OggS":
        return "video" if b"theora" in head[:512] else "audio"
    # FLAC / APE / WavPack / Musepack / AIFF / AMR / AU / MIDI / CAF
    if head[:4] in (b"fLaC", b"MAC ", b"wvpk", b"MPCK", b"MThd", b"caff", b".snd"):
        return "audio"
    if head[:3] == b"MP+":
        return "audio"
    if head[:4] == b"FORM" and head[8:12] in (b"AIFF", b"AIFC"):
        return "audio"
    if head[:6] == b"#!AMR\n":
        return "audio"
    # MP3: ID3 etiketi veya MPEG ses çerçeve senkronu
    if head[:3] == b"ID3":
        return "audio"
    if head[0] == 0xFF and (head[1] & 0xE0) == 0xE0 and (head[1] & 0x06) != 0:
        return "audio"
    # AAC ADTS
    if head[0] == 0xFF and (head[1] & 0xF6) == 0xF0:
        return "audio"
    # AC-3 / E-AC-3
    if head[:2] == b"\x0b\x77":
        return "audio"
    # DTS
    if head[:4] == b"\x7f\xfe\x80\x01":
        return "audio"
    # Ham H.264 / HEVC Annex-B
    if head[:4] == b"\x00\x00\x00\x01":
        nal = head[4]
        if (nal & 0x1F) in (7, 9):              # H.264 SPS / AUD
            return "video"
        if ((nal >> 1) & 0x3F) in (32, 33, 35):  # HEVC VPS / SPS / AUD
            return "video"
    return None


def classify(path: str | os.PathLike[str], detect_by_content: bool = True) -> str | None:
    """Bir dosya yolunu ``video``/``audio``/``None`` olarak sınıflandırır.

    Önce uzantıya bakılır; bilinmeyen uzantılarda (ve ``detect_by_content`` açıksa)
    içerik analizi yapılır.
    """
    ext = ext_of(path)
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in NON_MEDIA_EXTENSIONS or not detect_by_content:
        return None
    return sniff_media_kind(path)


def file_dialog_filter(tr) -> str:
    """QFileDialog için filtre metni. ``tr`` çeviri fonksiyonudur."""
    v = " ".join(f"*{e}" for e in sorted(VIDEO_EXTENSIONS))
    a = " ".join(f"*{e}" for e in sorted(AUDIO_EXTENSIONS))
    s = " ".join(f"*{e}" for e in sorted(SUBTITLE_EXTENSIONS - {'.txt'}))
    pl = "*.m3u *.m3u8 *.pls *.json"
    return ";;".join([
        f"{tr('filter.media')} ({v} {a})",
        f"{tr('filter.video')} ({v})",
        f"{tr('filter.audio')} ({a})",
        f"{tr('filter.subtitle')} ({s})",
        f"{tr('filter.playlist')} ({pl})",
        f"{tr('filter.all')} (*.*)",
    ])


def norm_path(p: str | os.PathLike[str]) -> str:
    """Karşılaştırma için normalleştirilmiş mutlak yol."""
    return os.path.normcase(os.path.abspath(os.fspath(p)))


def display_name(path_or_url: str) -> str:
    if is_stream_url(path_or_url):
        tail = path_or_url.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
        return tail or path_or_url
    return Path(path_or_url).stem or Path(path_or_url).name
