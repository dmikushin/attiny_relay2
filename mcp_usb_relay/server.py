#!/usr/bin/env python3
"""
MCP server for ATtiny85 CDC ACM USB relay control.

================================================================================
HOW THE RELAY API WORKS — read this before calling relay_on / relay_off.
================================================================================

The ATtiny85 controller is wired the same way for every relay it controls:

    relay_on  →  PB0 HIGH  (signal asserted)
    relay_off →  PB0 LOW   (signal released, default at power-up)

The PB0 signal is then routed to the relay coil. Whether HIGH or LOW
energizes the coil depends on the driver circuit, but the OBSERVABLE
result depends on the relay TYPE printed on the device's name:

    Normally OPEN (NO) relay   — at PB0 LOW the circuit is OPEN.
                                 At PB0 HIGH the circuit is CLOSED.
    Normally CLOSED (NC) relay — at PB0 LOW the circuit is CLOSED.
                                 At PB0 HIGH the circuit is OPEN.

"Normally" means "the state when the controller signal is LOW", which is
also the state at ATtiny power-up. The HIGH state is the inverse.

API → physical effect TRUTH TABLE:

    +-----------+-----+--------------------------+--------------------------+
    | API call  | PB0 | Normally OPEN relay      | Normally CLOSED relay    |
    +-----------+-----+--------------------------+--------------------------+
    | relay_off | LOW | circuit OPEN             | circuit CLOSED           |
    | relay_on  | HIGH| circuit CLOSED           | circuit OPEN             |
    +-----------+-----+--------------------------+--------------------------+

The relay TYPE is in the USB product name, e.g.:
    "Vive Flow USB cable: VCC ON/OFF Relay (normally closed)"
    "Vive Flow USB cable: Deep Flash Button Relay (normally open)"

USE CASE: HTC Vive Flow EDL deep flash cable
    • VCC relay (Normally Closed) — interrupts +5V on the USB cable.
        relay_off(VCC)  → LOW  → NC closed → power flows  → device ON
        relay_on(VCC)   → HIGH → NC open   → power cut    → device OFF
    • Deep Flash relay (Normally Open) — shorts USB D+ to GND.
        relay_off(DF)   → LOW  → NO open   → D+ free      → normal USB
        relay_on(DF)    → HIGH → NO closed → D+→GND short → EDL trigger

    Power-cycle into EDL mode:
        1. relay_on(VCC)        # power off (NC opened)
        2. wait 5s
        3. relay_on(DF)         # short D+ to GND (NO closed)
        4. wait 1s
        5. relay_off(VCC)       # power on (NC closed again)
        6. wait 3s              # SoC samples D+ at boot, enters EDL
        7. relay_off(DF)        # release D+ for USB enumeration

    Safe rest state for normal device operation:
        relay_off(VCC) + relay_off(DF)
        → power flows, D+ free, device boots Android normally

PERSISTENCE: closing the serial port resets PB0 to LOW (the cdc-acm
kernel driver clears the BREAK signal on close). This MCP server keeps
the serial connection open in `_open_ports` to preserve the asserted
state. Do NOT close the port between commands.

================================================================================

Tools:
  relay_list      — list connected relay devices (and their NO/NC type)
  relay_on        — drive PB0 HIGH (see truth table above)
  relay_off       — drive PB0 LOW  (default state)
  relay_set_name  — change USB device name (stored in EEPROM)
"""

import atexit
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

# Keep serial ports open so the break condition (relay state) is preserved.
# Closing the port causes the kernel cdc-acm driver to clear the break signal,
# which resets the relay to ON — the "sticking relay" bug.
_open_ports: dict[str, serial.Serial] = {}


def _get_serial(port: str) -> serial.Serial:
    """Get or open a cached serial connection for a port."""
    s = _open_ports.get(port)
    if s is not None and s.is_open:
        return s
    s = serial.Serial(port, 9600, timeout=1)
    _open_ports[port] = s
    return s


def _close_all_ports():
    for s in _open_ports.values():
        try:
            s.close()
        except Exception:
            pass
    _open_ports.clear()


atexit.register(_close_all_ports)


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
    """Drive PB0 HIGH on the controller.

    Effect on the relay (depends on type printed in the USB name):
      • Normally OPEN  → circuit CLOSED (contacts engage)
      • Normally CLOSED → circuit OPEN  (contacts disengage)

    See module docstring for the full truth table and Vive Flow EDL example.

    Args:
        device: Serial port (e.g. /dev/ttyACM1) or USB address (e.g. 1-2).
    """
    port = _resolve_device(device)
    s = _get_serial(port)
    s.break_condition = False
    return f"Relay ON: {port}"


@server.tool()
def relay_off(device: str) -> str:
    """Drive PB0 LOW on the controller (default state at ATtiny power-up).

    Effect on the relay (depends on type printed in the USB name):
      • Normally OPEN  → circuit OPEN   (rest state)
      • Normally CLOSED → circuit CLOSED (rest state)

    See module docstring for the full truth table and Vive Flow EDL example.

    Args:
        device: Serial port (e.g. /dev/ttyACM1) or USB address (e.g. 1-2).
    """
    port = _resolve_device(device)
    s = _get_serial(port)
    s.break_condition = True
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

    s = _get_serial(port)
    cmd = bytes([CMD_SET_NAME, len(name_bytes)]) + name_bytes
    s.write(cmd)
    s.flush()
    old_port = port
    # Device will reboot — close and remove from cache
    try:
        s.close()
    except Exception:
        pass
    _open_ports.pop(port, None)

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


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
