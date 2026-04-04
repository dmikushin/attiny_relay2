#!/usr/bin/env python3
"""
MCP server for ATtiny85 CDC ACM USB relay control.

Tools:
  relay_list      — list connected relay devices
  relay_on        — turn relay ON (PB0 LOW, conducting)
  relay_off       — turn relay OFF (PB0 HIGH, open)
  relay_set_name  — change USB device name (stored in EEPROM)
"""

import glob
import os
import time
import serial
from mcp.server.fastmcp import FastMCP

VID = 0x16C0
PID = 0x05E1
CMD_SET_NAME = 0xAA
NAME_MAX_LEN = 64

server = FastMCP("mcp-usb-relay", "USB relay controller for ATtiny85 DigiSpark devices")


def _sysfs_attr(tty_dev, attr):
    """Read USB device sysfs attribute for a tty device."""
    link = f"/sys/class/tty/{tty_dev}/device"
    if not os.path.islink(link):
        return None
    iface_dir = os.path.realpath(link)
    usb_dir = os.path.dirname(iface_dir)
    try:
        with open(os.path.join(usb_dir, attr)) as f:
            return f.read().strip()
    except OSError:
        return None


def _usb_address(tty_dev):
    """Get USB bus address like '1-2' for a tty device."""
    link = f"/sys/class/tty/{tty_dev}/device"
    if not os.path.islink(link):
        return None
    iface_dir = os.path.realpath(link)
    usb_dir = os.path.dirname(iface_dir)
    return os.path.basename(usb_dir)


def _find_relays():
    """Find all relay ttyACM devices matching VID/PID.

    Returns list of dicts with keys: port, usb_address, product, manufacturer.
    """
    results = []
    for tty in sorted(glob.glob("/dev/ttyACM*")):
        dev = os.path.basename(tty)
        vid = _sysfs_attr(dev, "idVendor")
        pid = _sysfs_attr(dev, "idProduct")
        if vid and pid and int(vid, 16) == VID and int(pid, 16) == PID:
            results.append({
                "port": tty,
                "usb_address": _usb_address(dev) or "?",
                "product": _sysfs_attr(dev, "product") or "",
                "manufacturer": _sysfs_attr(dev, "manufacturer") or "",
            })
    return results


def _resolve_device(device: str) -> str:
    """Resolve device identifier to a /dev/ttyACM path.

    Accepts:
      - /dev/ttyACMx  — used directly
      - ttyACMx       — prepends /dev/
      - USB address like '1-2' — looked up via sysfs
    """
    if device.startswith("/dev/"):
        return device
    if device.startswith("ttyACM"):
        return f"/dev/{device}"
    # Treat as USB address
    for relay in _find_relays():
        if relay["usb_address"] == device:
            return relay["port"]
    raise ValueError(f"No relay found at USB address '{device}'")


@server.tool()
def relay_list() -> str:
    """List all connected ATtiny85 USB relay devices with their ports, USB addresses, and names."""
    relays = _find_relays()
    if not relays:
        return "No relay devices found."
    lines = ["Port           USB Addr  Name"]
    lines.append("-" * 70)
    for r in relays:
        lines.append(f"{r['port']:<15}{r['usb_address']:<10}{r['product']}")
    return "\n".join(lines)


@server.tool()
def relay_on(device: str) -> str:
    """Turn relay ON (PB0 LOW, conducting). Accepts serial port path or USB address.

    Args:
        device: Serial port (e.g. /dev/ttyACM1) or USB address (e.g. 1-2).
    """
    port = _resolve_device(device)
    s = serial.Serial(port, 9600, timeout=1)
    s.break_condition = False
    s.close()
    return f"Relay ON: {port}"


@server.tool()
def relay_off(device: str) -> str:
    """Turn relay OFF (PB0 HIGH, open). Accepts serial port path or USB address.

    Args:
        device: Serial port (e.g. /dev/ttyACM1) or USB address (e.g. 1-2).
    """
    port = _resolve_device(device)
    s = serial.Serial(port, 9600, timeout=1)
    s.break_condition = True
    s.close()
    return f"Relay OFF: {port}"


@server.tool()
def relay_set_name(device: str, name: str) -> str:
    """Change USB device name (1-64 ASCII chars, stored in EEPROM). Device re-enumerates with new name.

    Args:
        device: Serial port (e.g. /dev/ttyACM1) or USB address (e.g. 1-2).
        name: New device name, up to 64 ASCII characters.
    """
    if not name or len(name) > NAME_MAX_LEN:
        return f"Error: name must be 1-{NAME_MAX_LEN} ASCII characters."
    port = _resolve_device(device)
    name_bytes = name.encode("ascii")

    s = serial.Serial(port, 9600, timeout=1)
    cmd = bytes([CMD_SET_NAME, len(name_bytes)]) + name_bytes
    s.write(cmd)
    s.flush()
    old_port = port
    s.close()

    # Wait for device to disappear and reappear
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not os.path.exists(old_port):
            break
        time.sleep(0.2)

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        relays = _find_relays()
        if relays:
            new = relays[0]
            return f"Name set to '{name}' on {new['port']} (USB {new['usb_address']})"
        time.sleep(0.5)

    return f"Name written but device did not reappear within timeout."


if __name__ == "__main__":
    server.run(transport="stdio")
