"""
LimeOBS sekme duman testi: uygulamayı açar, kayıtlı oturumla ana panele geçer, menüdeki her
sekmeyi iki kez gezer ve sekme başına HTTP istek sayısı/süresini yazdırır.
GTK uyarıları ve hatalar stderr'e düşer; çıktıyı bir dosyaya yönlendirip "WARNING|CRITICAL|Traceback"
diye aratın.

Kullanım: venv/bin/python scripts/tab_smoke_test.py 2> uyarilar.log
"""
import collections
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "akbim_frontend"), ROOT]
os.chdir(ROOT)

import akbim_api  # noqa: E402
from gi.repository import GLib  # noqa: E402

current = {"tab": "açılış"}
log = []
lock = threading.Lock()
_orig_request = akbim_api.session.request


def _timed_request(method, url, *args, **kwargs):
    started = time.perf_counter()
    try:
        return _orig_request(method, url, *args, **kwargs)
    finally:
        with lock:
            log.append((current["tab"], url.split("/", 3)[-1][:60], time.perf_counter() - started))


akbim_api.session.request = _timed_request

import main  # noqa: E402

app = main.AkbimApplication()
started_at = time.perf_counter()


def driver():
    win = app.window
    if win is None or win.main_stack.get_visible_child_name() != "dashboard":
        if time.perf_counter() - started_at > 25:
            print("ANA PANEL AÇILMADI (kayıtlı oturum/kimlik bilgisi yok mu?)")
            app.quit()
            return False
        return True
    rows = list(win.rows_map.keys())
    order = iter([(r, 1) for r in rows] + [(r, 2) for r in rows] + [(None, 0)])

    def step():
        row, visit = next(order)
        if row is None:
            GLib.timeout_add(500, app.quit)
            return False
        current["tab"] = f"{win.rows_map[row]}#{visit}"
        win.on_menu_activated(win.nav_list, row)
        return True

    current["tab"] = "giriş sonrası"
    GLib.timeout_add(3000, lambda: GLib.timeout_add(2500, step) and False)
    return False


GLib.timeout_add(500, driver)
app.run(None)

per_tab = collections.OrderedDict()
for tab, _url, dt in log:
    entry = per_tab.setdefault(tab, [0, 0.0])
    entry[0] += 1
    entry[1] += dt
print("\n===== SEKME BAŞINA HTTP İSTEKLERİ =====")
for tab, (count, total) in per_tab.items():
    print(f"{tab:22s} istek={count:3d}  toplam={total:5.2f}s")
print(f"\nTOPLAM İSTEK: {len(log)}")
for url, count in collections.Counter(u for _, u, _ in log).most_common(5):
    print(f"{count:3d}x {url}")
