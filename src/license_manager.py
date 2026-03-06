"""
License Manager — Modern Video Downloader
=========================================
Sistem validasi lisensi ONLINE via server Railway.
- Aktivasi: kirim kode + machine_id ke server → simpan respons lokal
- Verifikasi startup: ping server untuk cek status terbaru

Format kode: XXXXX-XXXXX-XXXXX-XXXXX-XXXXX  (25 chars + 4 dashes)
"""

import hashlib
import hmac
import json
import os
import platform
import uuid
import requests
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG — ganti SERVER_URL setelah deploy ke Railway
# ══════════════════════════════════════════════════════════════════════════════
SERVER_URL = os.environ.get(
    "LICENSE_SERVER_URL",
    "https://web-production-0375c.up.railway.app/"     # ← GANTI setelah deploy
)
REQUEST_TIMEOUT = 10   # detik

PLANS = {
    'T': {'name': 'Trial',      'days': 7,    'label': '7 Hari',      'color': '#f5a623'},
    'B': {'name': 'Basic',      'days': 30,   'label': '1 Bulan',     'color': '#4a9eff'},
    'P': {'name': 'Pro',        'days': 90,   'label': '3 Bulan',     'color': '#9b59b6'},
    'E': {'name': 'Enterprise', 'days': 365,  'label': '1 Tahun',     'color': '#2ecc71'},
    'L': {'name': 'Lifetime',   'days': None, 'label': 'Selamanya ∞', 'color': '#e74c3c'},
}

# Harus sama persis dengan LICENSE_SECRET di server Railway
_LOCAL_SECRET = os.environ.get("LICENSE_SECRET", "ganti_dengan_output_dari_perintah_diatas")


def _sign(payload: str) -> str:
    """Hitung 8-char HMAC signature — dipakai untuk live preview di dialog."""
    h = hmac.new(_LOCAL_SECRET.encode(), payload.encode('utf-8'), hashlib.sha256)
    return h.hexdigest()[:8].upper()


def get_machine_id() -> str:
    try:
        mac  = uuid.getnode()
        host = platform.node()
        raw  = f"{mac}-{host}-{platform.system()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    except Exception:
        return hashlib.sha256(b"fallback-machine").hexdigest()[:32]


class LicenseManager:
    """
    Validasi lisensi ONLINE.

    Alur aktivasi (sekali):
        activate(code) → POST /api/activate → simpan cache .license

    Alur startup (tiap buka app):
        is_activated() → POST /api/verify
        Jika offline → fallback cache (grace period 72 jam)
    """

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

    def validate_code(self, code: str) -> tuple[bool, dict | None, str]:
        """
        Validasi format & HMAC kode secara LOKAL (tanpa hit server).
        Dipakai untuk live preview di dialog saat user mengetik kode.

        Returns:
            (is_valid, plan_info_or_None, pesan)
        """
        raw = self._clean(code)
        if len(raw) != 25:
            return False, None, "Format kode salah — harus 25 karakter"

        plan_char   = raw[0]
        random_part = raw[1:17]
        sig_given   = raw[17:25]

        if plan_char not in PLANS:
            return False, None, "Tipe lisensi tidak dikenal"

        sig_expected = _sign(plan_char + random_part)
        if sig_given != sig_expected:
            return False, None, "Kode tidak valid atau telah dimodifikasi"

        plan_info = PLANS[plan_char]
        return True, plan_info, f"Kode valid — Paket {plan_info['name']} ({plan_info['label']})"

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

    def is_activated(self) -> bool:
        cache = self._load_cache()

        # Jika tidak ada cache sama sekali → belum pernah aktivasi
        if not cache:
            return False

        # Pastikan machine ID cocok
        if cache.get('machine_id') and cache['machine_id'] != self._machine_id:
            return False

        # Selalu coba verifikasi ke server selama ada kode tersimpan
        code = cache.get("code", "")
        if not code:
            return False

        try:
            resp = requests.post(
                f"{SERVER_URL}/api/verify",
                json={"code": code, "machine_id": self._machine_id},
                timeout=REQUEST_TIMEOUT
            )
            data = resp.json()

            if data.get("valid"):
                # Server konfirmasi valid — update cache dengan data terbaru
                self._save_cache({
                    **cache,
                    "plan":       data.get("plan",       cache.get("plan", "")),
                    "label":      data.get("label",      cache.get("label", "")),
                    "expires_at": data.get("expires_at", cache.get("expires_at")),
                    "lifetime":   data.get("lifetime",   cache.get("lifetime", False)),
                    "machine_id": self._machine_id,
                    "revoked":    False,   # tandai aktif kembali
                })
                return True
            else:
                # Server bilang tidak valid — tandai revoked di cache
                # JANGAN hapus file agar kode tetap tersimpan untuk re-check berikutnya
                self._save_cache({
                    **cache,
                    "revoked": True,
                })
                return False

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            # Offline → pakai cache, tapi jika sudah ditandai revoked tetap False
            if cache.get("revoked"):
                return False
            return self._cache_still_valid(cache)

        except Exception:
            if cache.get("revoked"):
                return False
            return self._cache_still_valid(cache)

    def get_license_info(self) -> dict | None:
        return self._load_cache()

    def get_status_text(self) -> str:
        cache = self._load_cache()
        if not cache:
            return "Tidak aktif"
        plan  = cache.get('plan', '')
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
