#!/usr/bin/env python3
"""
admin_tool.py — Developer/Admin Tool
====================================
Bikin KODE AKTIVASI KHUSUS ADMIN untuk Modern YT Downloader, supaya lo tidak
perlu buka website Railway. Ketik kodenya di dialog aktivasi biasa → aktif
Lifetime sebagai Administrator, tanpa server.

Cara kerja:
  * Tool ini membuat kode acak 25 karakter (diawali 'A', ~120 bit entropi).
  * Yang masuk ke source code (src/license_manager.py) hanya HASH-nya.
    Hash tidak bisa dibalik jadi kode, jadi aman walau repo publik.
  * Kode aslinya ditampilkan sekali + disimpan di admin_code.txt (di-.gitignore).

Pemakaian:
    python admin_tool.py new              # bikin kode admin (sekali saja)
    python admin_tool.py new --force      # ganti kode lama dengan yang baru
    python admin_tool.py verify <KODE>    # cek apakah suatu kode = kode admin
"""

import argparse
import os
import re
import secrets
import stat
import sys

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
MANAGER_FILE = os.path.join(BASE_DIR, "src", "license_manager.py")
CODE_FILE    = os.path.join(BASE_DIR, "admin_code.txt")

sys.path.insert(0, os.path.join(BASE_DIR, "src"))
import license_manager as lm  # noqa: E402

# Tanpa karakter yang mirip (0/O, 1/I) supaya gampang diketik/dibaca.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_raw() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(25 - len(lm.ADMIN_CODE_PREFIX)))
    return lm.ADMIN_CODE_PREFIX + body


def _format(raw: str) -> str:
    return "-".join(raw[i:i + 5] for i in range(0, 25, 5))


def cmd_new(force: bool):
    if lm.ADMIN_CODE_HASH and not force:
        sys.exit(
            "Kode admin sudah pernah dibuat (ADMIN_CODE_HASH sudah terisi) — dibatalkan.\n"
            "Pakai --force hanya kalau mau ganti kode (kode lama langsung tidak berlaku)."
        )

    raw  = _generate_raw()
    salt = secrets.token_bytes(16)
    new_value = f"{salt.hex()}${lm.hash_admin_code(raw, salt)}"

    with open(MANAGER_FILE, encoding="utf-8") as f:
        src = f.read()
    new_src, n = re.subn(
        r'^ADMIN_CODE_HASH\s*=\s*".*?"',
        f'ADMIN_CODE_HASH   = "{new_value}"',
        src, count=1, flags=re.MULTILINE,
    )
    if n != 1:
        sys.exit("Gagal menemukan baris ADMIN_CODE_HASH di src/license_manager.py")
    with open(MANAGER_FILE, "w", encoding="utf-8") as f:
        f.write(new_src)

    with open(CODE_FILE, "w", encoding="utf-8") as f:
        f.write(_format(raw) + "\n")
    try:
        os.chmod(CODE_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 600 (no-op di Windows)
    except OSError:
        pass

    print("✅ Kode admin dibuat:\n")
    print(f"      {_format(raw)}\n")
    print(f"   Disimpan juga di: {CODE_FILE}  (sudah di-.gitignore)")
    print("   Simpan di password manager. Hash-nya sudah dipasang ke src/license_manager.py.")
    print("   Commit license_manager.py (aman) — JANGAN commit admin_code.txt.")


def cmd_verify(code: str):
    mgr = lm.LicenseManager(BASE_DIR)
    ok = mgr._is_admin_code(code)
    print("✅ Ini kode admin yang valid." if ok else "❌ Bukan kode admin.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    ap  = argparse.ArgumentParser(description="Admin tool Modern YT Downloader")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="Bikin kode admin & pasang hash-nya ke app")
    p_new.add_argument("--force", action="store_true", help="Ganti kode admin lama")

    p_ver = sub.add_parser("verify", help="Cek apakah kode = kode admin")
    p_ver.add_argument("code")

    args = ap.parse_args()
    if args.cmd == "new":
        cmd_new(args.force)
    else:
        cmd_verify(args.code)
