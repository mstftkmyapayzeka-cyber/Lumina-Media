# Lumina Player 🎬

Windows 10/11 (64-bit) için VLC Media Player seviyesinde geniş format desteğine sahip, ancak modern Windows 11 Fluent tasarım diline ve modern kullanıcı deneyimine (UI/UX) sahip masaüstü medya oynatıcısı.

---

## 🌟 Öne Çıkan Özellikler

### 1. Kapsamlı Format ve Codec Desteği
- **Oynatma Motoru:** Dahili paketlenmiş **libVLC 3.x (64-bit)**. Bilgisayarınızda VLC kurulu olmasına gerek yoktur; gerekli tüm DLL ve eklentiler uygulamayla birlikte taşınır.
- **Video:** MP4, MKV, AVI, MOV, WMV, FLV, WebM, MPG/MPEG, TS, M2TS, MTS, VOB, 3GP, OGV, M4V, DIVX, RMVB, ASF vb.
- **Ses:** MP3, FLAC, WAV, AAC, M4A, OGG, OPUS, WMA, AIFF, APE, ALAC vb.
- **Altyazı:** SRT, ASS, SSA, VTT, SUB, IDX.
- **İçerik (Sihirli Bayt) Tespiti:** Uzantısı yanlış veya silinmiş medya dosyaları (`.dat` vb.) otomatik analiz edilerek oynatılır.
- **Donanım Hızlandırma:** D3D11VA, DXVA2, NVDEC donanım kod çözücüleri.

### 2. Akıllı Çalma Listesi ve Klasör Tarama
- **Doğal Sıralama (Natural Sort):** *Bölüm 2*, *Bölüm 10*'dan önce gelir.
- **Arka Planda Klasör Tarama:** Binlerce dosyalık klasörler arayüzü dondurmadan ayrı iş parçacığında (`QThread`) taranır.
- **Sürükle ve Bırak:** Dosyalar, klasörler veya altyazılar pencereye bırakıldığında anında listeye eklenir.
- **Çalma Modları:** Sırayla, Karışık (Shuffle), Listeyi Tekrarla, Tek Videoyu Tekrarla, Bitince Dur.
- **Dışa/İçe Aktarma:** M3U, M3U8 ve JSON çalma listesi desteği.

### 3. Gelişmiş Ses, Video ve Altyazı Kontrolleri
- **Türkçe Karakter Koruması:** CP1254, ISO-8859-9 ve UTF-8 altyazılar otomatik tespit edilir; `ğüşıöç` karakterleri bozulmaz.
- **10 Bantlı Ekolayzer:** Hazır ayarlar (Pop, Rock, Klasik, Bas Artırma vb.) ve özel frekans ayarları.
- **Video Renk Ayarları:** Parlaklık, kontrast, doygunluk ve gama sürgüleri.
- **%200 Ses Yükseltme:** Standart seviyenin üzerine çıkabilen hassas ses kontrolü.
- **Kaldığın Yerden Devam Et:** SQLite veritabanı ile son izlenen konumlar ve izlendi durumları hatırlanır.
- **Kare Kare İlerleme & Ekran Görüntüsü (S):** Tek tuşla yüksek kaliteli PNG/JPG anlık görüntü yakalama.

### 4. Modern Arayüz ve Windows Entegrasyonu
- **Modern Tasarım:** Antrasit koyu tema, özelleştirilebilir vurgu renkleri (Mavi, Mor, Kırmızı, Yeşil, Turuncu) ve açık tema seçeneği.
- **Çerçevesiz Pencere:** Özel başlık çubuğu, kenarlardan boyutlandırma ve çift tık tam ekran.
- **Otomatik Gizlenen Kontroller:** Fare hareketsiz kaldığında kontroller ve tam ekranda imleç pürüzsüzce gizlenir.
- **Tekil Örnek (Single Instance):** Çift tıklanan yeni videolar çalışan mevcut pencereye aktarılır.
- **Ekran Uykusunu Engelleme:** Video oynatılırken monitörün uyku moduna geçmesi önlenir.

---

## ⌨️ Klavye Kısayolları

| Tuş | Eylem |
|---|---|
| **Boşluk (Space)** | Oynat / Duraklat |
| **← / →** | 5 sn geri / ileri sar |
| **Shift + ← / →** | 30 sn geri / ileri sar |
| **Ctrl + ← / →** | 60 sn geri / ileri sar |
| **↑ / ↓** | Ses artır / azalt (+%5 / -%5) |
| **M** | Sesi kapat / aç (Mute) |
| **F** | Tam ekrana gir / çık |
| **P** | Çalma listesi yan panelini aç / kapat |
| **S** | Ekran görüntüsü al (Resimler klasörüne kaydeder) |
| **E** | Bir sonraki kareye ilerle (Frame step) |
| **N / B** | Sonraki / Önceki video |
| **[ / ]** | Oynatma hızını azalt / artır (0.25x – 4.0x) |
| **Ctrl + O** | Dosya Aç |
| **Ctrl + Shift + O**| Klasör Aç |
| **Ctrl + U** | Ağ Akışı / URL Aç |
| **Esc** | Tam ekrandan çık |

---

## 🛠️ Kurulum ve Geliştirme

### Gereksinimler
- Windows 10 veya Windows 11 (64-bit)
- Python 3.11 veya üzeri

### 1. Bağımlılıkları Kurma
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Taşınabilir libVLC Çalışma Zamanını Hazırlama
Uygulamanın çalışması ve bağımsız paketlenmesi için 64-bit libVLC'yi `vendor\vlc` klasörüne hazırlar:
```powershell
powershell -ExecutionPolicy Bypass -File tools\fetch_vlc.ps1
```

### 3. Uygulamayı Çalıştırma
```powershell
python -m lumina
```

### 4. Birim Testleri Çalıştırma
```powershell
pytest tests/
```

---

## 📦 Dağıtım ve Paketleme (.exe ve Installer)

Uygulamayı harici Python veya VLC kurulumuna ihtiyaç duymayan tek bir `.exe` ve Windows Installer'a dönüştürmek için:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

- **Çıktı klasörü:** `dist\LuminaPlayer\LuminaPlayer.exe`
- **Inno Setup:** Eğer sisteminizde Inno Setup 6 kuruluysa otomatik olarak tek tıkla kurulan `dist\LuminaPlayer_Setup_v0.2.0.exe` üretilir.

---

## ⚖️ Lisans ve Hukuki Bildirimler

### 1. libVLC (LGPL 2.1+) Lisans Uyumu
Lumina Player, medya kod çözme işlemleri için [VideoLAN](https://www.videolan.org/) projesinin **libVLC** kütüphanesini dinamik bağlama (`ctypes` / DLL) yöntemiyle kullanmaktadır. libVLC, GNU LGPL v2.1 lisansı kapsamındadır. Lumina Player'ın dağıtımında libVLC DLL dosyaları ve lisans metinleri bağımsız olarak korunur; kullanıcılar uygulama dizinindeki `vlc/` klasöründeki libVLC DLL'lerini güncel veya uyumlu başka sürümlerle değiştirebilme hakkına sahiptir.

### 2. DRM Bildirimi
Lumina Player yerel medya dosyaları ve şifresiz ağ akışları (HLS, RTSP, HTTP vb.) için tasarlanmıştır. Netflix, Spotify veya Amazon Prime gibi ticari platformların kullandığı tescilli **DRM (Widevine / PlayReady / FairPlay)** ile şifrelenmiş içerikleri oynatmaz.
