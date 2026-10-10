"""Lumina Player için modern çok çözünürlüklü .ico dosyası üretir."""
from pathlib import Path
from PIL import Image, ImageDraw

def generate_ico(dest_path: Path):
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for s in sizes:
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Yuvarlak köşeli modern arka plan (Derin lacivert / antrasit)
        margin = max(1, s // 16)
        radius = s // 4
        draw.rounded_rectangle([margin, margin, s - margin, s - margin], radius=radius, fill=(26, 29, 35, 255), outline=(59, 130, 246, 255), width=max(1, s // 32))

        # Canlı mavi Play üçgeni
        tri_left = s * 0.38
        tri_top = s * 0.28
        tri_right = s * 0.72
        tri_bottom = s * 0.72
        tri_mid_y = s * 0.50

        draw.polygon([(tri_left, tri_top), (tri_right, tri_mid_y), (tri_left, tri_bottom)], fill=(59, 130, 246, 255))
        images.append(img)

    images[0].save(str(dest_path), format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])
    print(f"İkon üretildi: {dest_path}")

if __name__ == "__main__":
    generate_ico(Path("lumina/resources/app.ico"))
