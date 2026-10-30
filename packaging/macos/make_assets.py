"""
macOS paketleme görsellerini üretir:
  - akbim_frontend/app_icon.icns  : Apple ikon ızgarasına uygun, yuvarlatılmış kare zeminli ikon
  - packaging/macos/dmg-background.png / dmg-background@2x.png : DMG penceresinin arka planı

Kullanım: venv/bin/python packaging/macos/make_assets.py [yazı_tipi.ttf]
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

ROOT = Path(__file__).resolve().parents[2]
LOGO = ROOT / "akbim_frontend" / "app_icon.png"
OUT_DIR = Path(__file__).resolve().parent
SS = 4  # kenar yumuşatma için süper örnekleme katsayısı


def rounded_mask(size, box, radius):
    big = Image.new("L", (size * SS, size * SS), 0)
    x0, y0, x1, y1 = (v * SS for v in box)
    ImageDraw.Draw(big).rounded_rectangle((x0, y0, x1, y1), radius=radius * SS, fill=255)
    return big.resize((size, size), Image.LANCZOS)


def vertical_gradient(size, top, bottom):
    g = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        g.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g.resize((size, size))


def make_icon():
    size = 1024
    # Apple macOS ikon ızgarası: 1024 tuval içinde 824x824 gövde, ~185 köşe yarıçapı
    body = (100, 92, 924, 916)
    radius = 185
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Yumuşak gölge
    shadow_mask = rounded_mask(size, (body[0], body[1] + 14, body[2], body[3] + 14), radius)
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow.putalpha(shadow_mask.point(lambda a: a * 0.28))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))

    # Zemin: çok açık, hafif yeşile çalan dikey degrade
    mask = rounded_mask(size, body, radius)
    fill = vertical_gradient(size, (255, 255, 255), (232, 242, 228)).convert("RGBA")
    fill.putalpha(mask)
    canvas.alpha_composite(fill)

    # İnce iç kenar çizgisi
    inner = rounded_mask(size, (body[0] + 2, body[1] + 2, body[2] - 2, body[3] - 2), radius - 2)
    ring = ImageChops.subtract(mask, inner)
    edge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    edge.putalpha(ring.point(lambda a: a * 0.10))
    canvas.alpha_composite(edge)

    # Logo: görünür piksellere göre kırp, gövdenin ~%68'ine sığdır, ortala
    logo = Image.open(LOGO).convert("RGBA")
    bbox = logo.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox()
    logo = logo.crop(bbox)
    target = int((body[2] - body[0]) * 0.68)
    scale = target / max(logo.size)
    logo = logo.resize((round(logo.width * scale), round(logo.height * scale)), Image.LANCZOS)
    cx = (body[0] + body[2]) // 2
    cy = (body[1] + body[3]) // 2
    canvas.alpha_composite(logo, (cx - logo.width // 2, cy - logo.height // 2))

    canvas.save(OUT_DIR / "icon-1024.png")
    canvas.save(
        ROOT / "akbim_frontend" / "app_icon.icns",
        sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)],
    )


def make_dmg_background(font_path):
    # create-dmg pencere boyutu 660x400; ikonlar (165,185) ve (495,185) merkezli
    for scale, name in ((1, "dmg-background.png"), (2, "dmg-background@2x.png")):
        w, h = 660 * scale, 400 * scale
        img = Image.new("RGB", (w, h), (247, 248, 246))
        d = ImageDraw.Draw(img)

        title = ImageFont.truetype(font_path, 22 * scale, index=0)
        sub = ImageFont.truetype(font_path, 14 * scale, index=0)
        t1 = "LimeOBS'u yükleyin"
        t2 = "Uygulamayı Uygulamalar klasörüne sürükleyip bırakın"
        d.text((w / 2, 48 * scale), t1, font=title, fill=(20, 20, 18), anchor="mm")
        d.text((w / 2, 78 * scale), t2, font=sub, fill=(110, 110, 104), anchor="mm")

        # İki ikon arasında ok
        y = 185 * scale
        x0, x1 = 262 * scale, 398 * scale
        col = (63, 174, 58)
        d.line((x0, y, x1 - 14 * scale, y), fill=col, width=4 * scale)
        d.polygon([(x1, y), (x1 - 20 * scale, y - 12 * scale), (x1 - 20 * scale, y + 12 * scale)], fill=col)

        d.text((w / 2, 352 * scale), "Açılmazsa: Sistem Ayarları → Gizlilik ve Güvenlik → Yine de Aç", font=sub, fill=(150, 150, 144), anchor="mm")
        img.save(OUT_DIR / name, dpi=(72 * scale, 72 * scale))


if __name__ == "__main__":
    make_icon()
    make_dmg_background(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/inter/Inter.ttc")
    print("Görseller üretildi:", OUT_DIR)
