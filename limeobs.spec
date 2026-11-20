# -*- mode: python ; coding: utf-8 -*-
# LimeOBS (Qt Quick) için tüm platformlarda ortak PyInstaller tanımı.
# Kullanım: pyinstaller --noconfirm --clean limeobs.spec
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

# Uygulama dosyaları main.py'nin beklediği düzende paketlenir: <paket>/akbim_frontend, <paket>/limeobs_qt
datas = [
    (str(ROOT / "akbim_api.py"), "."),
    (str(ROOT / "akbim_frontend" / "app_icon.png"), "akbim_frontend"),
    (str(ROOT / "limeobs_qt" / "icons.json"), "limeobs_qt"),
    (str(ROOT / "limeobs_qt" / "qml"), "limeobs_qt/qml"),
]
datas += [(str(p), "akbim_frontend") for p in (ROOT / "akbim_frontend").glob("*.py")]
datas += [(str(p), "limeobs_qt") for p in (ROOT / "limeobs_qt").glob("*.py")]

binaries = []
hiddenimports = [
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtSvg", "PySide6.QtNetwork", "PySide6.QtMultimedia",
    "keyring.backends", "pypdf", "bs4", "requests",
    # backend ve yardımcı modüller yol eklenerek içe aktarıldığı için açıkça belirtilir
    "api_bridge", "ai_assistant", "school_calendar", "food_menu", "security", "backend", "schedule_pdf",
    "telegram_notify",
]
for pkg in ("requests", "bs4", "keyring", "pypdf"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(
    [str(ROOT / "limeobs_qt" / "main.py")],
    pathex=[str(ROOT), str(ROOT / "akbim_frontend"), str(ROOT / "limeobs_qt")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "flask", "gi", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
    noarchive=False,
)
if not IS_MAC and not IS_WIN:
    # Linux: fontconfig/freetype sistemdekiyle kullanılır; paketlenen eski sürüm yeni sistem yapılandırmasını
    # okuyamayıp uyarı basıyor ve yazı tipi seçimini bozabiliyor.
    a.binaries = [b for b in a.binaries if not b[0].startswith(("libfontconfig", "libfreetype"))]
pyz = PYZ(a.pure)

if IS_WIN:
    # Windows: onedir taşınabilir klasör (Smart App Control engellerini önlemek için)
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="LimeOBS",
        icon=str(ROOT / "akbim_frontend" / "app_icon.ico"),
        console=False,
        upx=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="LimeOBS", upx=False)
else:
    name = "LimeOBS" if IS_MAC else "limeobs-bin"
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=name,
        console=False,
        upx=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name=name, upx=False)
    if IS_MAC:
        app = BUNDLE(
            coll,
            name="LimeOBS.app",
            icon=str(ROOT / "akbim_frontend" / "app_icon.icns"),
            bundle_identifier="com.kagan.limeobs",
            info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "1.1.1"},
        )
