#!/usr/bin/env python3
"""
lsrelay — list ATtiny85 CDC ACM USB relay devices.

Similar in spirit to lsusb: enumerates connected relay devices and
shows USB info, tty info, and the configured product name in a single
listing. Reads only sysfs — does not open serial ports, so it works
without dialout group membership.
"""

import glob
import os
import sys

# USB identifiers for V-USB CDC ACM (matches relay_control.relay)
VID = 0x16C0
PID = 0x05E1


def _read_attr(usb_dir, name):
    try:
        with open(os.path.join(usb_dir, name)) as f:
            return f.read().strip()
    except OSError:
        return ""


def _enumerate():
    """Walk /dev/ttyACM* and collect info for devices matching VID/PID.

    Returns a list of dicts with keys:
        tty, bus, dev, usb_addr, vid, pid, bcd, manufacturer, product
    """
    rows = []
    for tty in sorted(glob.glob("/dev/ttyACM*")):
        dev_name = os.path.basename(tty)
        link = f"/sys/class/tty/{dev_name}/device"
        if not os.path.islink(link):
            continue
        iface_dir = os.path.realpath(link)
        usb_dir = os.path.dirname(iface_dir)

        vid = _read_attr(usb_dir, "idVendor")
        pid = _read_attr(usb_dir, "idProduct")
        if not vid or not pid:
            continue
        try:
            if int(vid, 16) != VID or int(pid, 16) != PID:
                continue
        except ValueError:
            continue

        rows.append({
            "tty": tty,
            "bus": _read_attr(usb_dir, "busnum"),
            "dev": _read_attr(usb_dir, "devnum"),
            "usb_addr": os.path.basename(usb_dir),
            "vid": vid,
            "pid": pid,
            "bcd": _read_attr(usb_dir, "bcdDevice"),
            "manufacturer": _read_attr(usb_dir, "manufacturer"),
            "product": _read_attr(usb_dir, "product"),
        })
    return rows


def main(argv=None):
    rows = _enumerate()
    if not rows:
        print("No ATtiny relay devices found.", file=sys.stderr)
        return 1

    headers = ("TTY", "BUS", "DEV", "USB ADDR", "VID:PID", "MANUFACTURER", "NAME")
    table = [headers]
    for r in rows:
        table.append((
            r["tty"],
            r["bus"].zfill(3),
            r["dev"].zfill(3),
            r["usb_addr"],
            f"{r['vid']}:{r['pid']}",
            r["manufacturer"],
            r["product"],
        ))

    # Compute column widths (last column not padded — variable length name)
    widths = [max(len(row[i]) for row in table) for i in range(len(headers))]
    for ri, row in enumerate(table):
        parts = []
        for ci, cell in enumerate(row):
            if ci == len(row) - 1:
                parts.append(cell)
            else:
                parts.append(cell.ljust(widths[ci]))
        print("  ".join(parts))
        if ri == 0:
            print("  ".join("-" * w for w in widths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
