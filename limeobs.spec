# -*- mode: python ; coding: utf-8 -*-
# LimeOBS için tüm platformlarda ortak PyInstaller tanımı.
# Kullanım: pyinstaller --noconfirm --clean limeobs.spec
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

datas = [
    (str(ROOT / "akbim_frontend"), "akbim_frontend"),
    (str(ROOT / "akbim_api.py"), "."),
]
binaries = []
hiddenimports = ["gi.repository.Gtk", "gi.repository.Gdk", "gi.repository.Adw", "keyring.backends"]
for pkg in ("requests", "bs4", "keyring"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(
    [str(ROOT / "akbim_frontend" / "main.py")],
    pathex=[str(ROOT), str(ROOT / "akbim_frontend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # PyInstaller varsayılan olarak GTK 3 typelib'lerini arar; GTK 4 olduğunu açıkça belirtiyoruz.
    hooksconfig={
        "gi": {
            "module-versions": {"Gtk": "4.0", "Gdk": "4.0", "Gsk": "4.0"},
            "icons": ["Adwaita", "hicolor"],
            "themes": ["Adwaita"],
            "languages": ["tr", "en"],
        }
    },
    excludes=["tkinter", "flask"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if IS_WIN:
    # Windows: onedir taşınabilir klasör (Smart App Control engellerini önlemek için)
    win_icon = str(ROOT / "akbim_frontend" / "app_icon.ico") if (ROOT / "akbim_frontend" / "app_icon.ico").exists() else str(ROOT / "akbim_frontend" / "app_icon.png")
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="LimeOBS",
        icon=win_icon,
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
            info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "1.0.0"},
        )
