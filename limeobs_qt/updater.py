"""
LimeOBS masaüstü otomatik güncelleme.

- Paketli sürüm (AppImage / Windows taşınabilir / macOS .app): GitHub'daki son sürümü denetler, yeni ise kendi
  platformunun dosyasını indirir, uygulama kapanınca eskisinin yerine koyar ve yeniden başlatır.
- Kaynak koddan çalışma (git deposu): diskteki kod çalışan koddan yeniyse (version.py değişmişse) yeniden başlatmayı
  önerir. Pencere kapatılınca tepside kalan uygulama böylece eski kodla günlerce çalışmaz.
Kişisel veri gönderilmez; yalnızca GitHub'ın herkese açık sürüm bilgisi okunur.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

from version import VERSION

REPO = "kefy266/LimeOBS"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
FROZEN = getattr(sys, "frozen", False)
SOURCE_VERSION_FILE = Path(__file__).resolve().parent / "version.py"


def _tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def _asset_name():
    if sys.platform.startswith("win"):
        return "LimeOBS-Windows-Portable.zip"
    if sys.platform == "darwin":
        return "LimeOBS-macOS-arm64.zip"
    return "LimeOBS-x86_64.AppImage" if os.environ.get("APPIMAGE") else None


def mode():
    """'paket', 'kaynak' ya da None (güncellenemez: ör. AppImage dışı Linux paketi)."""
    if not FROZEN:
        return "kaynak"
    return "paket" if _asset_name() else None


def check():
    """Döner: {"version", "notes", "url", "size"} ya da güncel ise None. Hata olursa istisna fırlatır."""
    if mode() == "kaynak":
        text = SOURCE_VERSION_FILE.read_text(encoding="utf-8")
        disk = re.search(r'VERSION\s*=\s*"([^"]+)"', text)
        disk = disk.group(1) if disk else VERSION
        if _tuple(disk) > _tuple(VERSION):
            return {"version": disk, "notes": "Kaynak kod güncellendi; yeniden başlatınca yeni sürüm açılır.",
                    "url": "", "size": 0}
        return None
    if mode() is None:
        return None
    res = requests.get(API, timeout=15, headers={"Accept": "application/vnd.github+json", "User-Agent": "LimeOBS"})
    res.raise_for_status()
    rel = res.json()
    latest = (rel.get("tag_name") or "").lstrip("v")
    if _tuple(latest) <= _tuple(VERSION):
        return None
    asset = next((a for a in rel.get("assets") or [] if a.get("name") == _asset_name()), None)
    if not asset:
        return None
    return {"version": latest, "notes": (rel.get("body") or "").strip()[:600],
            "url": asset["browser_download_url"], "size": asset.get("size") or 0}


def download(info, progress=lambda done, total: None):
    """Güncellemeyi geçici klasöre indirir; indirilen dosyanın yolunu döner."""
    folder = Path(tempfile.mkdtemp(prefix="limeobs-guncelleme-"))
    target = folder / _asset_name()
    with requests.get(info["url"], stream=True, timeout=60, headers={"User-Agent": "LimeOBS"}) as res:
        res.raise_for_status()
        total = int(res.headers.get("Content-Length") or info.get("size") or 0)
        done = 0
        with open(target, "wb") as f:
            for chunk in res.iter_content(1 << 16):
                f.write(chunk)
                done += len(chunk)
                progress(done, total)
    return target


def restart_source():
    """Kaynak koddan çalışırken aynı komutla yeniden başlar."""
    subprocess.Popen([sys.executable, *sys.argv], start_new_session=True)


def install_and_restart(downloaded):
    """İndirilen paketi yerleştirir ve yeni sürümü başlatır. Çağıran taraf ardından uygulamadan çıkmalıdır."""
    downloaded = Path(downloaded)
    if os.environ.get("APPIMAGE"):
        current = Path(os.environ["APPIMAGE"])
        tmp = current.with_name(current.name + ".yeni")
        shutil.copyfile(downloaded, tmp)
        tmp.chmod(0o755)
        os.replace(tmp, current)  # çalışan AppImage'ın üzerine yazmak güvenlidir (dosya bağlı kalır)
        subprocess.Popen([str(current)], start_new_session=True)
        return

    pid = os.getpid()
    work = downloaded.parent
    if sys.platform.startswith("win"):
        with zipfile.ZipFile(downloaded) as z:
            z.extractall(work / "yeni")
        app_dir = Path(sys.executable).resolve().parent
        exe = app_dir / Path(sys.executable).name
        script = work / "guncelle.bat"
        script.write_text(
            "@echo off\r\n"
            f":bekle\r\ntasklist /FI \"PID eq {pid}\" | find \"{pid}\" >nul && (timeout /t 1 >nul & goto bekle)\r\n"
            f"robocopy \"{work / 'yeni' / 'LimeOBS'}\" \"{app_dir}\" /MIR /NJH /NJS /NFL /NDL >nul\r\n"
            f"start \"\" \"{exe}\"\r\n",
            encoding="utf-8")
        subprocess.Popen(["cmd", "/c", str(script)], creationflags=0x08000000)  # CREATE_NO_WINDOW
        return

    if sys.platform == "darwin":
        app = Path(sys.executable).resolve()
        while app.suffix != ".app" and app != app.parent:
            app = app.parent
        subprocess.run(["ditto", "-x", "-k", str(downloaded), str(work / "yeni")], check=True)
        new_app = work / "yeni" / "LimeOBS.app"
        script = work / "guncelle.sh"
        script.write_text(
            "#!/bin/sh\n"
            f"while kill -0 {pid} 2>/dev/null; do sleep 1; done\n"
            f"rm -rf \"{app}\" && mv \"{new_app}\" \"{app}\"\n"
            f"xattr -dr com.apple.quarantine \"{app}\" 2>/dev/null\n"
            f"open \"{app}\"\n",
            encoding="utf-8")
        script.chmod(0o755)
        subprocess.Popen(["/bin/sh", str(script)], start_new_session=True)
        return
    raise RuntimeError("Bu kurulum otomatik güncellenemiyor.")
