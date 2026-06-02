#!/usr/bin/env python3
"""
Manage UCOR (user correction) lists on the SMP02 via GPIB.

Supports uploading, activating, deactivating, deleting, and listing correction tables.

CSV Format
==========

Two CSV formats are supported. The first row MUST be a header.

Power-reading format (from sweep scripts):
  Frequency (MHz),Power Reading
  10,0.16 dBm
  100,0.21 dBm
Requires --setpoint to compute correction = setpoint - measured.

Corrections format (hand-crafted or pre-computed):
  Frequency (MHz),Correction (dB)
  10,-0.16
  100,-0.21
Used directly; no --setpoint needed.

UCOR correction = setpoint − measured. The SMP adds the correction to the
requested output level, so positive correction raises the output.

Manual ref: user manual §2.5.4, SCPI ref §3.6.11.2 SOURce:CORRection

Examples:
  # Upload and activate
  python smp_ucor.py upload 0_dBm.csv --setpoint 0 --name UCOR0 --activate

  # List all UCOR tables on the instrument
  python smp_ucor.py list

  # Activate a correction list
  python smp_ucor.py activate UCOR0

  # Deactivate UCOR (turn off correction without deleting)
  python smp_ucor.py deactivate

  # Delete a correction list
  python smp_ucor.py delete UCOR0
"""

import argparse
import csv
import sys
import time

from smp_common import check_errors, connect_smp, drain_err_queue

UCOR_MAX_DB = 6.0
UCOR_NAME_LEN = 7
COL_FREQ = "Frequency (MHz)"
COL_PWR = "Power Reading"
COL_CORR = "Correction (dB)"


def detect_csv_format(csv_path):
    """Return 'readings' or 'corrections' based on the header row."""
    with open(csv_path, newline="") as f:
        headers = next(csv.reader(f))
    if COL_CORR in headers:
        return "corrections"
    if COL_PWR in headers:
        return "readings"
    raise ValueError(f"Unrecognised CSV columns: {headers}")


def load_corrections(csv_path, setpoint_dbm=None):
    """Return (freq_hz_list, correction_db_list)."""
    fmt = detect_csv_format(csv_path)
    if fmt == "readings" and setpoint_dbm is None:
        raise ValueError(f"'{csv_path}' has '{COL_PWR}' format — --setpoint required")

    freqs, corrections = [], []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            freq_mhz = float(row[COL_FREQ])
            if fmt == "readings":
                measured = float(row[COL_PWR].replace(" dBm", ""))
                corr = setpoint_dbm - measured
            else:
                corr = float(row[COL_CORR])
            freqs.append(int(freq_mhz * 1e6))
            corrections.append(corr)
    return freqs, corrections


def clamp_corrections(freqs, corrections):
    """Clamp corrections to ±UCOR_MAX_DB."""
    clamped = []
    for freq_hz, corr in zip(freqs, corrections, strict=False):
        if abs(corr) > UCOR_MAX_DB:
            print(
                f"  WARNING: {corr:+.2f} dB @ {freq_hz / 1e6:.0f} MHz exceeds "
                f"±{UCOR_MAX_DB} dB — clamping"
            )
            corr = max(-UCOR_MAX_DB, min(UCOR_MAX_DB, corr))
        clamped.append(corr)
    return clamped


def get_catalog(dev):
    """Return set of UCOR list names."""
    reply = dev.query(":SOUR:CORR:CSET:CAT?").strip()
    if not reply:
        return set()
    return {t.strip().strip('"').upper() for t in reply.split(",") if t.strip()}


def cmd_upload(args):
    """Upload a UCOR list from CSV."""
    args.name = args.name.upper()
    if len(args.name) > UCOR_NAME_LEN:
        print(f"ERROR: name '{args.name}' exceeds {UCOR_NAME_LEN} chars")
        sys.exit(1)

    freqs, corrections = load_corrections(args.csv, args.setpoint)
    corrections = clamp_corrections(freqs, corrections)

    MIN_HZ = 10_000_001
    filtered = [(f, c) for f, c in zip(freqs, corrections, strict=False) if f >= MIN_HZ]
    if len(filtered) < len(freqs):
        for f, _ in [
            (f, c) for f, c in zip(freqs, corrections, strict=False) if f < MIN_HZ
        ]:
            print(f"  WARNING: dropping {f / 1e6:.0f} MHz (below 10 MHz min)")
        freqs, corrections = map(list, zip(*filtered, strict=False))

    try:
        dev = connect_smp()
    except ConnectionError as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    print(f"Writing UCOR list '{args.name}' ({len(freqs)} points)...")
    dev.write(f':SOUR:CORR:CSET:SEL "{args.name}"')
    time.sleep(0.2)

    dev.write(
        ":SOUR:CORR:CSET:DATA:FREQ "
        + f"{','.join(f'{int(round(f / 1e6))}MHz' for f in freqs)}"
    )
    time.sleep(2.0)

    dev.write(
        ":SOUR:CORR:CSET:DATA:POW " + f"{','.join(f'{c:.2f}dB' for c in corrections)}"
    )
    time.sleep(2.0)

    if not check_errors(dev, "upload"):
        dev.close()
        sys.exit(1)

    if args.activate:
        dev.write(":SOUR:CORR:STAT ON")
        check_errors(dev, "activate")

    print("  ✓ Done")
    dev.close()


def cmd_list_ucor(args):
    """List all UCOR lists."""
    try:
        dev = connect_smp()
    except ConnectionError as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    catalog = get_catalog(dev)
    if not catalog:
        print("No UCOR lists")
    else:
        print(f"UCOR lists ({len(catalog)}):")
        for name in sorted(catalog):
            print(f"  • {name}")
    dev.close()


def cmd_activate(args):
    """Activate a UCOR list."""
    name = args.name.upper()
    try:
        dev = connect_smp()
    except ConnectionError as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    if name not in get_catalog(dev):
        print(f"ERROR: '{name}' not found")
        dev.close()
        sys.exit(1)

    dev.write(f':SOUR:CORR:CSET:SEL "{name}"')
    dev.write(":SOUR:CORR:STAT ON")
    check_errors(dev, "activate")
    print(f"  ✓ '{name}' activated")
    dev.close()


def cmd_deactivate(args):
    """Deactivate UCOR."""
    try:
        dev = connect_smp()
    except ConnectionError as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    dev.write(":SOUR:CORR:STAT OFF")
    check_errors(dev, "deactivate")
    print("  ✓ UCOR deactivated")
    dev.close()


def cmd_delete(args):
    """Delete a UCOR list."""
    name = args.name.upper()
    try:
        dev = connect_smp()
    except ConnectionError as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    if name not in get_catalog(dev):
        print(f"ERROR: '{name}' not found")
        dev.close()
        sys.exit(1)

    if not args.force:
        answer = input(f"Delete '{name}'? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted")
            dev.close()
            sys.exit(0)

    dev.write(":SOUR:CORR:STAT OFF")
    drain_err_queue(dev)
    dev.write(f':SOUR:CORR:CSET:DEL "{name}"')
    check_errors(dev, "delete")
    print(f"  ✓ '{name}' deleted")
    dev.close()


def main():
    parser = argparse.ArgumentParser(
        description="Manage UCOR lists on the SMP02 via GPIB"
    )
    subparsers = parser.add_subparsers(dest="cmd", help="Command")

    # upload
    up = subparsers.add_parser("upload", help="Upload UCOR from CSV")
    up.add_argument("csv", help="CSV file")
    up.add_argument("--name", required=True, help="List name")
    up.add_argument("--setpoint", type=float, help="Power setpoint (dBm)")
    up.add_argument("--activate", action="store_true")

    # list
    subparsers.add_parser("list", help="List UCOR tables")

    # activate
    act = subparsers.add_parser("activate", help="Activate a UCOR list")
    act.add_argument("name", help="List name")

    # deactivate
    subparsers.add_parser("deactivate", help="Deactivate UCOR")

    # delete
    dlt = subparsers.add_parser("delete", help="Delete a UCOR list")
    dlt.add_argument("name", help="List name")
    dlt.add_argument("--force", action="store_true")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    if args.cmd == "upload":
        cmd_upload(args)
    elif args.cmd == "list":
        cmd_list_ucor(args)
    elif args.cmd == "activate":
        cmd_activate(args)
    elif args.cmd == "deactivate":
        cmd_deactivate(args)
    elif args.cmd == "delete":
        cmd_delete(args)


if __name__ == "__main__":
    main()
