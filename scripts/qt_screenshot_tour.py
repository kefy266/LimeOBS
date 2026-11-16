"""
Qt arayüzünün sayfalarını sırayla açıp ekran görüntüsü alır ve çalışma sırasında çıkan
QML uyarılarını yazdırır. Kayıtlı oturumla ana panele geçer (önce bir kez giriş yapılmış olmalı).

Kullanım:
  venv/bin/python scripts/qt_screenshot_tour.py ÇIKTI_KLASÖRÜ home,exams,homework+detail:2340
Adım biçimi: <sayfa>[+detail:<ödev id>]   (ör. homework+detail:2340 → ödev ayrıntısını açar)
"""
import runpy
import sys
from pathlib import Path

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, QTimer, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication

OUT = Path(sys.argv[1])
STEPS = sys.argv[2].split(",")
OUT.mkdir(parents=True, exist_ok=True)
sys.argv = ["limeobs"]
messages = []


def on_message(mode, ctx, text):
    if mode != QtMsgType.QtDebugMsg and "Fontconfig" not in text:
        messages.append(text)


def find_shell(window):
    stack = [window.contentItem()]
    while stack:
        item = stack.pop()
        if item.property("pages") is not None and item.property("sidebarOpen") is not None:
            return item
        stack.extend(item.childItems())


def tour(app, tries=0):
    windows = [w for w in app.topLevelWindows() if w.isVisible()]
    shell = find_shell(windows[0]) if windows else None
    if shell is None:
        if tries > 60:
            print("ANA EKRAN AÇILMADI", flush=True)
            app.quit()
            return
        QTimer.singleShot(500, lambda: tour(app, tries + 1))
        return
    window = windows[0]

    def step(k):
        if k >= len(STEPS):
            print("\n".join(sorted(set(messages))) or "UYARI YOK", flush=True)
            app.quit()
            return
        page, _, extra = STEPS[k].partition("+")
        shell.setProperty("current", page)
        if extra.startswith("detail:"):
            hw_id = int(extra.split(":")[1])

            def open_detail():
                found = [o for o in window.findChildren(QObject) if o.metaObject().className().startswith("HomeworkDetail")]
                for obj in found:
                    if obj.property("homeworkId") is not None:
                        QMetaObject.invokeMethod(obj, "show", Q_ARG("QVariant", hw_id), Q_ARG("QVariant", "Ödev"))
                        return
                print(f"HomeworkDetail bulunamadı ({len(found)})", flush=True)
            QTimer.singleShot(1500, open_detail)
        name = STEPS[k].replace(":", "-").replace("+", "_")
        QTimer.singleShot(6000, lambda: (window.grabWindow().save(str(OUT / f"{k}_{name}.png")), step(k + 1)))

    step(0)


_exec = QGuiApplication.exec


def exec_with_tour(*_):
    app = QGuiApplication.instance()
    qInstallMessageHandler(on_message)
    QTimer.singleShot(1000, lambda: tour(app))
    return _exec()


QGuiApplication.exec = exec_with_tour
runpy.run_path(str(Path(__file__).resolve().parent.parent / "limeobs_qt" / "main.py"), run_name="__main__")
