"""Haftalık ders programını yatay A4 PDF olarak çizer (QPdfWriter + QPainter, ek bağımlılık yok)."""

from datetime import date
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QImage, QColor, QFont, QFontMetricsF, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Ders adına göre sabit, yumuşak renkler (aynı ders her zaman aynı renk)
_PALETTE = ["#e3f1dc", "#dcebf7", "#fbe7d3", "#efe1f5", "#fbf3cf", "#d9f1ee",
            "#f7dde2", "#e6e6f7", "#e9f0d5", "#f3e3d7", "#dbeef7", "#f0ecdf"]
_ACCENT = QColor("#3f8f34")
_TEXT = QColor("#24231f")
_MUTED = QColor("#6b6a64")
_LINE = QColor("#dedbd0")


def _color_for(lesson, cache):
    if lesson not in cache:
        cache[lesson] = QColor(_PALETTE[len(cache) % len(_PALETTE)])
    return cache[lesson]


def _time_key(t):
    try:
        h, m = t.split("-")[0].split(":")
        return int(h) * 60 + int(m)
    except (ValueError, IndexError):
        return 9999


LOGO = Path(__file__).resolve().parent / "qml" / "LimeUI" / "logo.png"


def _logo():
    """Logoyu şeffaf kenarlarından kırpar."""
    img = QImage(str(LOGO))
    if img.isNull():
        return img
    img = img.convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if img.pixelColor(x, y).alpha() > 20:
                xs.append(x)
                ys.append(y)
    if not xs:
        return img
    return img.copy(min(xs), min(ys), max(xs) - min(xs) + 2, max(ys) - min(ys) + 2)


def render(path, week, student="", school="", class_name="", term=""):
    """week: Pazartesiden başlayan 5–7 elemanlı liste (hafta sonu dersi varsa 6 ya da 7); her biri [{"time": "08:30-09:10", "lesson": ..., "teacher": ...}]."""
    times = sorted({l["time"] for day in week for l in day if l.get("time")}, key=_time_key)
    if not times:
        raise ValueError("Ders programında ders bulunamadı.")
    grid = {(i, l["time"]): l for i, day in enumerate(week) for l in day}

    writer = QPdfWriter(str(path))
    writer.setTitle("Ders Programı")
    writer.setCreator("LimeOBS")
    writer.setResolution(300)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape, QMarginsF(0, 0, 0, 0)))

    p = QPainter(writer)
    p.setRenderHint(QPainter.Antialiasing)
    W, H = writer.width(), writer.height()
    mm = writer.resolution() / 25.4
    margin = 12 * mm

    def font(pt, weight=QFont.Normal):
        f = QFont("Inter")
        f.setStyleHint(QFont.SansSerif)
        f.setPointSizeF(pt)
        f.setWeight(weight)
        return f

    # --- Başlık: solda logo + LimeOBS + başlık, sağda okul / sınıf / öğrenci
    x0, y = margin, margin
    head_h = 16 * mm
    logo = _logo()
    text_x = x0
    if not logo.isNull():
        lh = head_h
        lw = lh * logo.width() / logo.height()
        p.drawImage(QRectF(x0, y, lw, lh), logo)
        text_x = x0 + lw + 4 * mm
    p.setPen(_ACCENT)
    p.setFont(font(10, QFont.Bold))
    p.drawText(QRectF(text_x, y, W / 2, head_h * 0.38), Qt.AlignLeft | Qt.AlignBottom, "LimeOBS")
    p.setPen(_TEXT)
    p.setFont(font(20, QFont.Bold))
    title = "Ders Programı" + (f" — {class_name}" if class_name else "")
    p.drawText(QRectF(text_x, y + head_h * 0.38, W / 2, head_h * 0.62), Qt.AlignLeft | Qt.AlignTop, title)

    right = QRectF(W / 2, y, W / 2 - margin, head_h)
    lines = [(school, font(12, QFont.Bold), _TEXT),
             (" • ".join(x for x in (f"{class_name} sınıfı" if class_name else "", term) if x), font(10, QFont.DemiBold), _ACCENT),
             (student, font(9.5), _MUTED)]
    lines = [l for l in lines if l[0]]
    heights = [QFontMetricsF(f, writer).height() * 1.15 for _, f, _ in lines]
    ty = y + (head_h - sum(heights)) / 2
    for (text, f, c), lh in zip(lines, heights):
        p.setFont(f)
        p.setPen(c)
        p.drawText(QRectF(right.left(), ty, right.width(), lh), Qt.AlignRight | Qt.AlignVCenter, text)
        ty += lh
    y += head_h + 3 * mm
    p.setPen(QPen(_ACCENT, 0.6 * mm))
    p.drawLine(int(x0), int(y), int(W - margin), int(y))
    y += 5 * mm

    # --- Tablo
    footer_h = 8 * mm
    time_w = 24 * mm
    day_h = 9 * mm
    gap = 1.4 * mm
    col_w = (W - 2 * margin - time_w) / len(week)
    row_h = min(22 * mm, (H - y - margin - footer_h - day_h) / len(times))

    p.setFont(font(10.5, QFont.DemiBold))
    for i, name in enumerate(DAY_NAMES[:len(week)]):
        r = QRectF(x0 + time_w + i * col_w + gap / 2, y, col_w - gap, day_h - gap)
        p.setPen(Qt.NoPen)
        p.setBrush(_ACCENT)
        p.drawRoundedRect(r, 1.6 * mm, 1.6 * mm)
        p.setPen(QColor("white"))
        p.drawText(r, Qt.AlignCenter, name)
    y += day_h

    colors = {}
    for k, t in enumerate(times):
        ry = y + k * row_h
        p.setPen(_MUTED)
        p.setFont(font(9, QFont.DemiBold))
        p.drawText(QRectF(x0, ry, time_w - 2 * mm, row_h / 2), Qt.AlignRight | Qt.AlignBottom, f"{k + 1}. ders")
        p.setFont(font(8))
        p.drawText(QRectF(x0, ry + row_h / 2, time_w - 2 * mm, row_h / 2), Qt.AlignRight | Qt.AlignTop,
                   t.replace("-", " – "))
        for i in range(len(week)):
            r = QRectF(x0 + time_w + i * col_w + gap / 2, ry + gap / 2, col_w - gap, row_h - gap)
            cell = grid.get((i, t))
            if not cell or not cell.get("lesson"):
                p.setPen(QPen(_LINE, 0.25 * mm, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(r, 1.6 * mm, 1.6 * mm)
                continue
            p.setPen(Qt.NoPen)
            p.setBrush(_color_for(cell["lesson"], colors))
            p.drawRoundedRect(r, 1.6 * mm, 1.6 * mm)
            inner = r.adjusted(2.5 * mm, 1.5 * mm, -2.5 * mm, -1.5 * mm)
            teacher = cell.get("teacher") or ""
            # Ders adı ve öğretmen birlikte ölçülüp hücrenin dikey ortasına yerleştirilir
            name_font = font(10.5, QFont.DemiBold)
            for pt in (10.5, 9.5, 8.5):
                name_font = font(pt, QFont.DemiBold)
                name_box = QFontMetricsF(name_font, writer).boundingRect(
                    QRectF(0, 0, inner.width(), 10 * inner.height()), int(Qt.AlignLeft | Qt.TextWordWrap), cell["lesson"])
                if name_box.height() <= inner.height() * (0.62 if teacher else 1):
                    break
            teach_h = QFontMetricsF(font(8), writer).height() if teacher else 0
            space = 0.6 * mm if teacher else 0
            top = inner.top() + max(0, (inner.height() - name_box.height() - space - teach_h) / 2)
            p.setPen(_TEXT)
            p.setFont(name_font)
            p.drawText(QRectF(inner.left(), top, inner.width(), name_box.height()), Qt.AlignLeft | Qt.TextWordWrap,
                       cell["lesson"])
            if teacher:
                p.setPen(_MUTED)
                p.setFont(font(8))
                p.drawText(QRectF(inner.left(), top + name_box.height() + space, inner.width(), teach_h),
                           Qt.AlignLeft | Qt.AlignVCenter,
                           QFontMetricsF(font(8), writer).elidedText(teacher, Qt.ElideRight, inner.width()))

    # --- Alt bilgi
    p.setPen(_MUTED)
    p.setFont(font(8))
    p.drawText(QRectF(margin, H - margin - footer_h / 2, W - 2 * margin, footer_h / 2), Qt.AlignLeft | Qt.AlignVCenter,
               f"LimeOBS ile oluşturuldu • {date.today().strftime('%d.%m.%Y')}")
    p.end()
