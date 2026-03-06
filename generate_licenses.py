#!/usr/bin/env python3
"""
generate_licenses.py — Developer Tool
======================================
Gunakan script ini untuk membuat kode lisensi yang valid sebelum
mengirimkannya ke customer.

Jalankan:
    python generate_licenses.py

Atau langsung dari terminal tanpa prompt:
    python generate_licenses.py --plan P --count 5
"""

import argparse
import sys
import os

# Tambahkan src/ ke path agar bisa import LicenseManager
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from license_manager import LicenseManager, PLANS


# ── Warna terminal ─────────────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    DIM    = "\033[2m"

PLAN_COLORS = {
    'T': C.YELLOW,
    'B': C.BLUE,
    'P': C.CYAN,
    'E': C.GREEN,
    'L': C.RED,
}


def print_banner():
    print(f"""
{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════╗
║       Modern YT Downloader — License Generator      ║
╚══════════════════════════════════════════════════╝{C.RESET}
""")


def print_plans():
    print(f"{C.BOLD}Paket tersedia:{C.RESET}")
    for key, plan in PLANS.items():
        color = PLAN_COLORS.get(key, C.WHITE)
        print(f"  {color}{C.BOLD}[{key}]{C.RESET}  {plan['name']:<12} {C.DIM}({plan['label']}){C.RESET}")
    print()


def interactive_mode(mgr: LicenseManager):
    """Mode interaktif dengan prompt."""
    print_banner()
    print_plans()

    # Pilih plan
    while True:
        choice = input(f"{C.BOLD}Pilih paket {C.DIM}[T/B/P/E/L]{C.RESET}{C.BOLD}: {C.RESET}").strip().upper()
        if choice in PLANS:
            break
        print(f"{C.RED}  Pilihan tidak valid. Masukkan salah satu: T, B, P, E, L{C.RESET}")

    # Jumlah kode
    while True:
        try:
            count_str = input(f"{C.BOLD}Jumlah kode yang dibuat {C.DIM}[1-100]{C.RESET}{C.BOLD}: {C.RESET}").strip()
            count = int(count_str)
            if 1 <= count <= 100:
                break
            print(f"{C.RED}  Masukkan angka antara 1 dan 100{C.RESET}")
        except ValueError:
            print(f"{C.RED}  Harus berupa angka{C.RESET}")

    generate_and_print(mgr, choice, count)


def generate_and_print(mgr: LicenseManager, plan: str, count: int):
    """Generate dan tampilkan kode lisensi."""
    plan_info = PLANS[plan]
    color     = PLAN_COLORS.get(plan, C.WHITE)

    print(f"\n{C.BOLD}Generating {count} kode untuk paket "
          f"{color}{plan_info['name']}{C.RESET}{C.BOLD} ({plan_info['label']})...{C.RESET}\n")

    separator = "─" * 52
    print(f"{C.DIM}{separator}{C.RESET}")

    codes = []
    for i in range(1, count + 1):
        code = mgr.generate_code(plan)
        codes.append(code)
        print(f"  {C.DIM}{i:>3}.{C.RESET}  {color}{C.BOLD}{code}{C.RESET}")

    print(f"{C.DIM}{separator}{C.RESET}")
    print(f"\n{C.GREEN}✅  {count} kode berhasil dibuat.{C.RESET}")

    # Tawarkan simpan ke file
    save = input(f"\n{C.BOLD}Simpan ke file .txt? {C.DIM}[y/N]{C.RESET}{C.BOLD}: {C.RESET}").strip().lower()
    if save == 'y':
        _save_to_file(codes, plan_info)


def _save_to_file(codes: list[str], plan_info: dict):
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename  = f"licenses_{plan_info['name'].lower()}_{timestamp}.txt"

    with open(filename, 'w') as f:
        f.write(f"Modern YT Downloader — License Codes\n")
        f.write(f"Plan  : {plan_info['name']} ({plan_info['label']})\n")
        f.write(f"Date  : {datetime.now().strftime('%d %b %Y %H:%M:%S')}\n")
        f.write(f"Count : {len(codes)}\n")
        f.write("=" * 40 + "\n\n")
        for i, code in enumerate(codes, 1):
            f.write(f"{i:>3}. {code}\n")

    print(f"{C.GREEN}💾  Tersimpan di: {C.BOLD}{filename}{C.RESET}")


def cli_mode(plan: str, count: int, mgr: LicenseManager):
    """Mode CLI tanpa interaksi."""
    plan = plan.upper()
    if plan not in PLANS:
        print(f"Error: plan '{plan}' tidak dikenal. Gunakan: T, B, P, E, L", file=sys.stderr)
        sys.exit(1)
    generate_and_print(mgr, plan, count)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate license codes untuk Modern YT Downloader',
        add_help=True,
    )
    parser.add_argument('--plan',  '-p', type=str, default=None,
                        help='Tipe paket: T, B, P, E, L')
    parser.add_argument('--count', '-n', type=int, default=1,
                        help='Jumlah kode yang dibuat (default: 1)')
    args = parser.parse_args()

    mgr = LicenseManager()

    if args.plan:
        cli_mode(args.plan, args.count, mgr)
    else:
        try:
            interactive_mode(mgr)
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C.DIM}Dibatalkan.{C.RESET}")
            sys.exit(0)
