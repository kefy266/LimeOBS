from akbim_api import ensure_login, load_index

if not ensure_login():
    raise SystemExit("Giriş yapılamadı!")

data = load_index()
schedule = data.get("data", {}).get("lessonSchedule", {}).get("data", {})
x_info = schedule.get("xInfo", [])
y_info = schedule.get("yInfo", [])
lessons = schedule.get("data", [])

if not lessons or not y_info:
    print("Ders programı verisi bulunamadı.")
    raise SystemExit()

print("=" * 60)
print(f"{'HAFTALIK DERS PROGRAMI':^60}")
print("=" * 60)

for day_index, day_data in enumerate(y_info, start=1):
    day_name = day_data[0] if len(day_data) > 0 else f"Gün {day_index}"
    day_date = day_data[1] if len(day_data) > 1 else ""
    date_str = f" ({day_date})" if day_date else ""

    print(f"\n[{day_name}{date_str}]")
    print("-" * 60)

    day_lessons = sorted(
        [l for l in lessons if l.get("y") == day_index],
        key=lambda item: item.get("x", 0)
    )

    if not day_lessons:
        print("  Ders bulunmuyor.")
        continue

    for l in day_lessons:
        x_idx = l.get("x", 1) - 1
        slot = x_info[x_idx][0] if 0 <= x_idx < len(x_info) else "??:?? - ??:??"
        
        texts = l.get("text", [])
        teacher = texts[0] if len(texts) > 0 else "-"
        subject = texts[1] if len(texts) > 1 else "-"

        print(f"  {slot:<15} | {subject:<22} | {teacher}")

print("\n" + "=" * 60)