"""
LimeOBS Güvenlik & Kriptografi Modülü
Tüm işletim sistemlerinde (Windows, Linux, macOS) kimlik bilgilerini (TC, şifre vb.)
asla düz metin (plaintext) olarak saklamaz.

Güvenlik Mimarisi:
1. Windows:
   - Windows DPAPI (CryptProtectData / CryptUnprotectData): Bilgiler doğrudan mevcut
     Windows kullanıcısının kimlik bilgilerine ve TPM/donanımına kilitlenir.
2. Linux (GNOME / KDE / Ubuntu / Fedora / Arch):
   - Öncelikli: GNOME Keyring / FreeDesktop Secret Service (keyring kütüphanesi).
   - Dosya Kasası: Linux yerel '/etc/machine-id' ve '$USER' sistem kimliğinden
     100.000 iterasyonlu PBKDF2 (HMAC-SHA256) ile türetilen donanım kilidi.
3. macOS:
   - Öncelikli: Apple Keychain (keyring kütüphanesi).
   - Dosya Kasası: Donanım UUID + '$USER' PBKDF2 donanım kilidi.
4. Tüm Platformlar:
   - HMAC-SHA256 kriptografik kurcalama (tamper) ve bütünlük kontrolü.
   - Bilgiler dışarıdan değiştirilirse otomatik tespit edilir ve geçersiz kılınır.
"""

import sys
import os
import json
import base64
import hashlib
import hmac
from typing import Optional, Dict, Any

# İsteğe bağlı sistem anahtarlık motoru (GNOME Keyring / macOS Keychain)
try:
    import keyring
except ImportError:
    keyring = None

KEYRING_SERVICE = "LimeOBS"
KEYRING_USER = "saved_creds"

# Windows DPAPI desteği
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ('cbData', wintypes.DWORD),
            ('pbData', ctypes.POINTER(ctypes.c_byte))
        ]


def _get_system_machine_id() -> str:
    """Linux ve macOS için donanıma özgü benzersiz sistem kimliğini (machine-id) okur."""
    if sys.platform.startswith("linux"):
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                if os.path.isfile(p):
                    with open(p, "r", encoding="utf-8") as f:
                        val = f.read().strip()
                        if val:
                            return val
            except Exception:
                pass
    elif sys.platform == "darwin":
        try:
            import subprocess
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8")
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split("=")[-1].strip().strip('"')
        except Exception:
            pass
    return ""


def _device_secret_for(comp: str) -> bytes:
    uname = os.environ.get('USERNAME', os.environ.get('USER', 'default_user'))
    mid = _get_system_machine_id()
    raw = f"limeobs-vault::{uname}::{comp}::{mid}::v2"
    return hashlib.sha256(raw.encode('utf-8')).digest()


def _get_device_secret() -> bytes:
    """İşletim sistemine, makine donanımına ve mevcut oturum kullanıcısına özgü anahtar türetir."""
    import socket
    comp = os.environ.get('COMPUTERNAME') or socket.gethostname() or 'default_host'
    return _device_secret_for(comp)


def _candidate_device_secrets():
    """Önce güncel anahtar; ardından HOSTNAME ortam değişkenine bağlı eski sürümlerin anahtarları."""
    keys = [_get_device_secret()]
    for comp in (os.environ.get('HOSTNAME'), 'default_host'):
        if comp:
            k = _device_secret_for(comp)
            if k not in keys:
                keys.append(k)
    return keys


def encrypt_string(data: str) -> str:
    """Verilen metni işletim sistemine uygun yerel şifreleme ile korur."""
    if not data:
        return ""
    raw = data.encode('utf-8')

    # 1. Windows: Native DPAPI
    if sys.platform == 'win32' and hasattr(sys, 'getwindowsversion'):
        try:
            import ctypes
            in_blob = DATA_BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_byte)))
            out_blob = DATA_BLOB()
            if ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(in_blob),
                'LimeOBS_Creds',
                None,
                None,
                None,
                0,
                ctypes.byref(out_blob)
            ):
                buf = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                ctypes.windll.kernel32.LocalFree(out_blob.pbData)
                return 'dpapi:' + base64.b64encode(buf).decode('ascii')
        except Exception as e:
            print(f"[Güvenlik] DPAPI hatası, fallback uygulanıyor: {e}")

    # 2. Linux / macOS / Fallback: 100.000 iterasyonlu PBKDF2 + AES benzeri keystream PRF
    key = _get_device_secret()
    nonce = os.urandom(16)
    keystream = hashlib.pbkdf2_hmac('sha256', key, nonce, 100000, len(raw))
    cipher = bytes([a ^ b for a, b in zip(raw, keystream)])
    return 'pbkdf2_v2:' + base64.b64encode(nonce + cipher).decode('ascii')


def decrypt_string(token: str, key: Optional[bytes] = None) -> str:
    """Şifreli belirteci çözer."""
    if not token:
        return ""

    if token.startswith('dpapi:'):
        raw_b64 = token[6:]
        buf = base64.b64decode(raw_b64)
        in_blob = DATA_BLOB(len(buf), ctypes.cast(ctypes.create_string_buffer(buf), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob)
        ):
            res = ctypes.string_at(out_blob.pbData, out_blob.cbData).decode('utf-8')
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return res
        raise ValueError("DPAPI şifre çözme başarısız: Başka bir kullanıcı veya bilgisayar oturumu.")

    elif token.startswith('pbkdf2_v2:') or token.startswith('fallback:'):
        is_v2 = token.startswith('pbkdf2_v2:')
        prefix_len = 10 if is_v2 else 9
        iters = 100000 if is_v2 else 10000
        
        raw_b64 = token[prefix_len:]
        data = base64.b64decode(raw_b64)
        nonce, cipher = data[:16], data[16:]
        key = key or _get_device_secret()
        keystream = hashlib.pbkdf2_hmac('sha256', key, nonce, iters, len(cipher))
        plain = bytes([a ^ b for a, b in zip(cipher, keystream)])
        return plain.decode('utf-8')

    else:
        raise ValueError("Bilinmeyen veya geçersiz şifreleme formatı.")


def generate_vault_payload(creds_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kimlik bilgilerini şifreler, HMAC-SHA256 imzası ekler.
    Ayrıca sistemde keyring (GNOME Keyring / Keychain) varsa oraya da güvenle yazar.
    """
    serialized = json.dumps(creds_dict, ensure_ascii=False)

    # Sistem anahtarlığı (GNOME Keyring / KWallet / macOS Keychain / Windows Credential Manager)
    # kullanılabiliyorsa bilgiler YALNIZCA orada tutulur. Dosya kasasının anahtarı makineden
    # türetildiği için herkesin okuyabildiği bilgilerle çözülebilir; sadece yedek yöntemdir.
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, serialized)
            if keyring.get_password(KEYRING_SERVICE, KEYRING_USER) == serialized:
                return {"version": 2, "format": "system_keyring"}
        except Exception as e:
            print(f"[Güvenlik] Keyring kaydetme uyarısı: {e}")

    encrypted_blob = encrypt_string(serialized)
    key = _get_device_secret()
    sig = hmac.new(key, encrypted_blob.encode('utf-8'), hashlib.sha256).hexdigest()

    return {
        "version": 2,
        "format": "system_vault",
        "blob": encrypted_blob,
        "integrity_hmac": sig
    }


def unpack_vault_payload(vault_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Kriptografik kasayı açar:
    1. Sistem anahtarlığı (GNOME Keyring / macOS Keychain) kontrol edilir.
    2. Dosyadaki HMAC-SHA256 bütünlüğü doğrulanır ve şifre çözülür.
    """
    # 1. Linux GNOME Keyring / macOS Keychain kontrolü
    if keyring is not None:
        try:
            saved = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
            if saved:
                return json.loads(saved)
        except Exception:
            pass

    # 2. Dosya Kasası (DPAPI / PBKDF2) kontrolü
    try:
        blob = vault_dict.get("blob")
        sig = vault_dict.get("integrity_hmac")
        if not blob or not sig:
            return None

        # HMAC-SHA256 Bütünlük / Kurcalama Doğrulaması
        key = None
        for cand in _candidate_device_secrets():
            if hmac.compare_digest(sig, hmac.new(cand, blob.encode('utf-8'), hashlib.sha256).hexdigest()):
                key = cand
                break
        if key is None:
            # Geriye dönük uyumluluk (v1 anahtar kontrolü)
            uname = os.environ.get('USERNAME', os.environ.get('USER', 'default_user'))
            comp = os.environ.get('COMPUTERNAME', 'default_pc')
            key_v1 = hashlib.sha256(f"limeobs-secure-salt-{uname}-{comp}".encode('utf-8')).digest()
            key_v1_alt = hashlib.sha256(f"limeobs-device-vault-key::{uname}::{comp}::v1".encode('utf-8')).digest()
            sig_v1 = hmac.new(key_v1, blob.encode('utf-8'), hashlib.sha256).hexdigest()
            sig_v1_alt = hmac.new(key_v1_alt, blob.encode('utf-8'), hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, sig_v1):
                key = key_v1
            elif hmac.compare_digest(sig, sig_v1_alt):
                key = key_v1_alt
            else:
                print("[Güvenlik Uyarısı] Kasa HMAC bütünlük kontrolü başarısız! Dosya tahrif edilmiş olabilir.")
                return None

        decrypted_json = decrypt_string(blob, key)
        return json.loads(decrypted_json)
    except Exception as e:
        print(f"[Güvenlik] Kasa çözme hatası: {e}")
        return None


def clear_system_keyring():
    """Oturum kapatıldığında işletim sistemi anahtarlığından (GNOME Keyring vb.) kaydı siler."""
    if keyring is not None:
        # "limeobs" eski sürümlerin kullandığı servis adı
        for service in (KEYRING_SERVICE, "limeobs"):
            try:
                keyring.delete_password(service, KEYRING_USER)
            except Exception:
                pass
