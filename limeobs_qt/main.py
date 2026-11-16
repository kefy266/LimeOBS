"""LimeOBS — Qt Quick arayüzü. Çalıştırma: venv/bin/python limeobs_qt/main.py"""
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPainter
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtSvg import QSvgRenderer

if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    DATA_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "limeobs"
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BUNDLE_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(BUNDLE_DIR), str(BUNDLE_DIR / "akbim_frontend")]

import akbim_api  # noqa: E402

akbim_api.COOKIE_FILE = str(DATA_DIR / "akbim_session.pkl")

QT_DIR = BUNDLE_DIR / "limeobs_qt"
sys.path.insert(0, str(QT_DIR))
from backend import Backend  # noqa: E402


class IconProvider(QQuickImageProvider):
    """'image://icon/<ad>?<renk>' → icons.json'daki çizgi ikonu verilen renkte çizer (Orbital'deki gibi)."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self.paths = json.loads((QT_DIR / "icons.json").read_text(encoding="utf-8"))

    def requestImage(self, icon_id, size, requested_size):
        name, _, color = icon_id.partition("?")
        qcolor = QColor(color or "#000000")
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
               f'stroke="{qcolor.name(QColor.NameFormat.HexRgb)}" stroke-opacity="{qcolor.alphaF():.3f}" '
               'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
               f'{self.paths.get(name, "")}</svg>')
        side = max(requested_size.width(), requested_size.height(), 18)
        image = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter)
        painter.end()
        if size is not None:
            size.setWidth(side)
            size.setHeight(side)
        return image


def main():
    QGuiApplication.setApplicationName("LimeOBS")
    QGuiApplication.setOrganizationName("LimeOBS")
    QGuiApplication.setDesktopFileName("com.kagan.limeobs")
    app = QGuiApplication(sys.argv)
    app.setWindowIcon(QIcon(str(BUNDLE_DIR / "akbim_frontend" / "app_icon.png")))

    backend = Backend(DATA_DIR)
    qmlRegisterSingletonInstance(Backend, "LimeBackend", 1, 0, "App", backend)

    engine = QQmlApplicationEngine()
    engine.addImageProvider("icon", IconProvider())
    engine.addImportPath(str(QT_DIR / "qml"))
    engine.loadFromModule("LimeUI", "Main")
    if not engine.rootObjects():
        sys.exit(1)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
