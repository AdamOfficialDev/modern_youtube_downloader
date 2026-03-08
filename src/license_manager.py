"""
License Manager — Modern Video Downloader
=========================================
Sistem validasi lisensi ONLINE via server Railway.
Semua validasi dilakukan 100% di server — tidak ada secret di client.

- Preview  : GET  /api/preview  → info kode dari DB (tanpa aktivasi)
- Aktivasi : POST /api/activate → binding kode ke machine_id
- Verifikasi: POST /api/verify  → cek status tiap startup

Format kode: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX  (25 chars + 4 dashes)
"""

import hashlib
import json
import os
import requests
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
SERVER_URL = os.environ.get(
    "LICENSE_SERVER_URL",
    "https://web-production-0375c.up.railway.app"
)
REQUEST_TIMEOUT = 10   # detik — activate & verify
PREVIEW_TIMEOUT =  5   # detik — preview dialog

# Semua info plan diambil dari server — dict ini hanya untuk UI badge statis
PLANS = {
    'T': {'name': 'Trial',      'days': 7,    'label': '7 Hari',      'color': '#f5a623'},
    'B': {'name': 'Basic',      'days': 30,   'label': '1 Bulan',     'color': '#4a9eff'},
    'P': {'name': 'Pro',        'days': 90,   'label': '3 Bulan',     'color': '#9b59b6'},
    'E': {'name': 'Enterprise', 'days': 365,  'label': '1 Tahun',     'color': '#2ecc71'},
    'L': {'name': 'Lifetime',   'days': None, 'label': 'Selamanya ∞', 'color': '#e74c3c'},
}


def get_machine_id() -> str:
    """
    Generate machine ID yang STABIL — tidak berubah meski restart atau ganti network.

    Prioritas:
    1. Windows Machine GUID (dari registry) — paling stabil, unik per instalasi Windows
    2. Linux machine-id — stabil di Linux
    3. Hostname + platform sebagai fallback
    """
    import platform
    import hashlib

    system = platform.system()

    # ── Windows: baca Machine GUID dari registry ──────────────────────────────
    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography"
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            if guid:
                return hashlib.sha256(guid.encode()).hexdigest()[:32]
        except Exception:
            pass

    # ── Linux: baca /etc/machine-id ───────────────────────────────────────────
    if system == "Linux":
        try:
            with open("/etc/machine-id") as f:
                mid = f.read().strip()
                if mid:
                    return hashlib.sha256(mid.encode()).hexdigest()[:32]
        except Exception:
            pass

    # ── macOS: baca IOPlatformUUID ────────────────────────────────────────────
    if system == "Darwin":
        try:
            import subprocess
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                stderr=subprocess.DEVNULL
            ).decode()
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    uid = line.split('"')[-2]
                    return hashlib.sha256(uid.encode()).hexdigest()[:32]
        except Exception:
            pass

    # ── Fallback: hostname + platform (tidak ideal tapi lebih stabil dari MAC) ─
    try:
        raw = f"{platform.node()}-{platform.system()}-{platform.machine()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    except Exception:
        return hashlib.sha256(b"fallback-machine").hexdigest()[:32]


class LicenseManager:
    GRACE_PERIOD_HOURS = 72

    def __init__(self, base_path: str = "."):
        self.base_path     = str(base_path)
        self._license_file = os.path.join(self.base_path, '.license')
        self._machine_id   = get_machine_id()

    def _clean(self, code: str) -> str:
        return code.strip().upper().replace('-', '').replace(' ', '')

    def _format_code(self, raw: str) -> str:
        raw = self._clean(raw)
        if len(raw) != 25:
            return raw
        return f"{raw[0:5]}-{raw[5:10]}-{raw[10:15]}-{raw[15:20]}-{raw[20:25]}"

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def get_active_code(self) -> str | None:
        cache = self._load_cache()
        return cache.get("code") if cache else None

    def check_internet(self) -> bool:
        """
        Cek koneksi ke server Railway.
        Dipakai dialog untuk tampilkan status internet real-time.
        Timeout pendek (3s) agar tidak blocking UI.
        """
        try:
            requests.get(f"{SERVER_URL}/health", timeout=3)
            return True
        except Exception:
            return False

    def _save_cache(self, data: dict):
        data['cached_at'] = datetime.now().isoformat()
        try:
            with open(self._license_file, 'w') as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _load_cache(self) -> dict | None:
        if not os.path.exists(self._license_file):
            return None
        try:
            with open(self._license_file) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _cache_still_valid(self, cache: dict) -> bool:
        cached_at_str = cache.get('cached_at')
        if not cached_at_str:
            return False
        try:
            cached_at   = datetime.fromisoformat(cached_at_str)
            hours_since = (datetime.now() - cached_at).total_seconds() / 3600
            return hours_since <= self.GRACE_PERIOD_HOURS
        except ValueError:
            return False

    # ── Preview: fetch info kode dari server sebelum aktivasi ─────────────────

    def fetch_code_info(self, code: str) -> dict:
        """
        Fetch info kode dari PostgreSQL via endpoint /api/preview.
        GET /api/preview?code=XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
        Tidak butuh machine_id, tidak butuh HMAC.
        """
        formatted = self._format_code(code)
        if len(self._clean(code)) != 25:
            return {"ok": False, "found": False, "valid": False,
                    "error": "format", "msg": "Format kode salah"}

        url = f"{SERVER_URL}/api/preview"
        print(f"[LicenseMgr] preview → {url}?code={formatted}")

        try:
            resp = requests.get(url, params={"code": formatted},
                                timeout=PREVIEW_TIMEOUT)

            print(f"[LicenseMgr] status={resp.status_code} body={resp.text[:300]}")

            if resp.status_code == 200:
                return self._parse_preview_response(resp.json())

            if resp.status_code == 404:
                return {"ok": False, "found": False, "valid": False,
                        "error": "endpoint_missing",
                        "msg": ""}   # dialog akan tampilkan pesan netral

            return {"ok": False, "found": False, "valid": False,
                    "error": f"http_{resp.status_code}", "msg": ""}

        except requests.exceptions.Timeout:
            print(f"[LicenseMgr] timeout ({PREVIEW_TIMEOUT}s)")
            return {"ok": False, "found": False, "valid": False,
                    "error": "timeout", "msg": ""}
        except requests.exceptions.ConnectionError as e:
            print(f"[LicenseMgr] connection error: {e}")
            return {"ok": False, "found": False, "valid": False,
                    "error": "offline", "msg": ""}
        except Exception as e:
            print(f"[LicenseMgr] unexpected: {e}")
            return {"ok": False, "found": False, "valid": False,
                    "error": str(e), "msg": ""}

    def _parse_preview_response(self, data: dict) -> dict:
        if not data.get("found"):
            return {"ok": True, "found": False, "valid": False,
                    "msg": "Kode tidak ditemukan — periksa kembali atau hubungi developer"}

        plan_name = data.get("plan_name", "")
        label     = data.get("label", "")
        status    = data.get("status", "inactive")
        lifetime  = data.get("lifetime", False)
        expires   = data.get("expires_at")

        # Double-check: jika expires_at sudah lewat, paksa status jadi expired
        # (safety net jika server lama tidak return status expired dengan benar)
        if expires and not lifetime:
            try:
                if datetime.now() > datetime.fromisoformat(expires):
                    status = "expired"
            except Exception:
                pass

        base = {"ok": True, "found": True, "plan_name": plan_name,
                "label": label, "status": status,
                "expires_at": expires, "lifetime": lifetime}

        if status == "revoked":
            return {**base, "valid": False,
                    "msg": "Kode ini telah dinonaktifkan — hubungi developer"}

        if status == "expired":
            return {**base, "valid": False,
                    "msg": f"Kode sudah kadaluarsa — tidak bisa digunakan lagi"}

        if status == "inactive":
            msg = f"Paket {plan_name} ({label}) · Siap diaktivasi"
        elif lifetime:
            msg = f"Paket {plan_name} · Selamanya ∞"
        elif expires:
            try:
                exp_dt    = datetime.fromisoformat(expires)
                remaining = (exp_dt - datetime.now()).days
                date_str  = exp_dt.strftime('%d %b %Y')
                msg = f"Paket {plan_name} ({label}) · Berakhir {date_str} ({remaining} hari lagi)"
            except Exception:
                msg = f"Paket {plan_name} ({label})"
        else:
            msg = f"Paket {plan_name} ({label})"

        return {**base, "valid": True, "msg": msg}

    # ── Activate ──────────────────────────────────────────────────────────────

    def activate(self, code: str) -> tuple[bool, str]:
        formatted = self._format_code(code)
        if len(self._clean(code)) != 25:
            return False, "Format kode salah — harus 25 karakter (XXXXX-XXXXX-XXXXX-XXXXX-XXXXX)"
        try:
            resp = requests.post(
                f"{SERVER_URL}/api/activate",
                json={"code": formatted, "machine_id": self._machine_id, "app_version": "1.0.0"},
                timeout=REQUEST_TIMEOUT
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("success"):
                self._save_cache({
                    "code":       formatted,
                    "plan":       data.get("plan", ""),
                    "label":      data.get("label", ""),
                    "expires_at": data.get("expires_at"),
                    "lifetime":   data.get("lifetime", False),
                    "machine_id": self._machine_id,
                })
                return True, f"✅ {data.get('message', 'Aktivasi berhasil!')}"
            return False, data.get("message", "Aktivasi gagal.")
        except requests.exceptions.ConnectionError:
            return False, "❌ Tidak dapat terhubung ke server.\nPastikan koneksi internet aktif."
        except requests.exceptions.Timeout:
            return False, "❌ Server tidak merespons (timeout).\nCoba beberapa saat lagi."
        except Exception as e:
            return False, f"❌ Error: {str(e)}"

    # ── Verify (startup) ──────────────────────────────────────────────────────

    def is_activated(self) -> bool:
        """
        Cek validitas lisensi.

        Urutan:
        1. expires_at di cache sudah lewat? → BLOK (data ini ditulis server sendiri saat aktivasi)
        2. Hit server /api/verify → server PostgreSQL yang memutuskan
        3. Server bilang tidak valid (reason apapun) → BLOK
        4. Offline → grace period 72 jam
        """
        cache = self._load_cache()
        if not cache:
            return False
        if cache.get('machine_id') and cache['machine_id'] != self._machine_id:
            return False
        code = cache.get("code", "")
        if not code:
            return False

        # ── STEP 1: Cek expires_at dari cache ─────────────────────────────────
        # expires_at ini ditulis oleh SERVER saat aktivasi/verify — bukan kalkulasi lokal.
        # Jika sudah lewat, tidak perlu tanya server — pasti expired.
        expires_at_str = cache.get("expires_at")
        lifetime       = cache.get("lifetime", False)
        if expires_at_str and not lifetime:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now() > expires_at:
                    print(f"[LicenseManager] BLOCKED — expires_at from cache: {expires_at_str}")
                    self._save_cache({**cache,
                                      "expired": True,
                                      "invalid_reason": "expired",
                                      "invalid_at": datetime.now().isoformat()})
                    return False
            except Exception:
                pass

        # ── STEP 2: Hit server ────────────────────────────────────────────────
        try:
            resp = requests.post(
                f"{SERVER_URL}/api/verify",
                json={"code": code, "machine_id": self._machine_id},
                timeout=REQUEST_TIMEOUT
            )
            data   = resp.json()
            reason = data.get("reason", "unknown")

            if data.get("valid"):
                # Server konfirmasi valid — update cache dengan data terbaru
                self._save_cache({
                    **cache,
                    "plan":           data.get("plan",       cache.get("plan", "")),
                    "label":          data.get("label",      cache.get("label", "")),
                    "expires_at":     data.get("expires_at", cache.get("expires_at")),
                    "lifetime":       data.get("lifetime",   cache.get("lifetime", False)),
                    "machine_id":     self._machine_id,
                    "invalid_reason": None,
                    "expired":        False,
                    "revoked":        False,
                })
                return True

            # Server bilang tidak valid — reason apapun → BLOK
            print(f"[LicenseManager] BLOCKED by server — reason: {reason}, msg: {data.get('message')}")
            self._save_cache({
                **cache,
                "expired":        reason == "expired",
                "revoked":        reason == "revoked",
                "invalid_reason": reason,
                "invalid_at":     datetime.now().isoformat(),
            })
            return False

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            print(f"[LicenseManager] offline — grace period fallback")
            return self._cache_still_valid(cache)

        except Exception as e:
            print(f"[LicenseManager] verify error: {e}")
            return self._cache_still_valid(cache)

    # ── Info helpers ──────────────────────────────────────────────────────────

    def get_license_info(self) -> dict | None:
        return self._load_cache()

    def get_status_text(self) -> str:
        cache = self._load_cache()
        if not cache:
            return "Tidak aktif"
        plan = cache.get('plan', '')
        if cache.get('lifetime'):
            return f"Aktif — {plan} (Lifetime ∞)"
        expires_str = cache.get('expires_at')
        if expires_str:
            try:
                exp_dt    = datetime.fromisoformat(expires_str)
                remaining = (exp_dt - datetime.now()).days
                if remaining < 0:
                    return "Lisensi sudah kadaluarsa"
                date_str = exp_dt.strftime('%d %b %Y')
                return f"Aktif — {plan} | Berakhir: {date_str} ({remaining} hari lagi)"
            except ValueError:
                pass
        return f"Aktif — {plan} ({cache.get('label', '')})"
