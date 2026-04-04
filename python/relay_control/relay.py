"""
ATtiny85 CDC ACM Relay Controller — Python control library.

Controls an induction relay connected to PB0 of a DigiSpark ATtiny85
via USB CDC ACM (ttyACM) interface.

Relay logic:
    Serial Break active  -> PB0 HIGH -> relay OFF (Normally Open)
    Serial Break cleared -> PB0 LOW  -> relay ON

Name change protocol (sent as raw bytes on the ttyACM data channel):
    0xAA <length> <name bytes...>
    Device writes name to EEPROM and reboots.
"""

import glob
import os
import time
import serial

# USB identifiers for V-USB CDC ACM
VID = 0x16C0
PID = 0x05E1

# Command protocol
CMD_SET_NAME = 0xAA
NAME_MAX_LEN = 30


def _read_sysfs(tty_path, attr):
    """Read a USB device sysfs attribute for a tty device.

    /sys/class/tty/ttyACMx/device -> USB interface dir
    Parent of interface dir -> USB device dir (has idVendor, product, etc.)
    """
    dev = os.path.basename(tty_path)
    device_link = f"/sys/class/tty/{dev}/device"
    if not os.path.islink(device_link):
        return None
    interface_dir = os.path.realpath(device_link)
    usb_device_dir = os.path.dirname(interface_dir)
    path = os.path.join(usb_device_dir, attr)
    try:
        with open(path) as f:
            return f.read().strip()
    except (OSError, IOError):
        return None


def find_devices():
    """Find all ttyACM devices matching our VID/PID.

    Returns list of (tty_path, product_name) tuples.
    """
    results = []
    for tty in sorted(glob.glob("/dev/ttyACM*")):
        vid = _read_sysfs(tty, "idVendor")
        pid = _read_sysfs(tty, "idProduct")
        if vid and pid:
            if int(vid, 16) == VID and int(pid, 16) == PID:
                product = _read_sysfs(tty, "product") or ""
                results.append((tty, product))
    return results


class RelayControl:
    """Control interface for ATtiny85 CDC ACM relay module."""

    def __init__(self, port=None):
        """Open connection to relay device.

        Args:
            port: ttyACM device path. If None, auto-detect first matching device.
        """
        if port is None:
            devices = find_devices()
            if not devices:
                raise RuntimeError("No ATtiny Relay device found")
            port = devices[0][0]
        self.port = port
        self._serial = serial.Serial(port, baudrate=9600, timeout=1)

    def close(self):
        """Close the serial connection."""
        if self._serial and self._serial.is_open:
            self._serial.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def name(self):
        """Read current USB product name from sysfs."""
        return _read_sysfs(self.port, "product") or ""

    def relay_on(self):
        """Turn relay ON (PB0 LOW) by clearing serial break."""
        self._serial.break_condition = False

    def relay_off(self):
        """Turn relay OFF (PB0 HIGH) by asserting serial break."""
        self._serial.break_condition = True

    def set_name(self, name, reconnect_timeout=15):
        """Change USB device name. Device reboots after receiving the command.

        Args:
            name: New device name (1-30 ASCII characters).
            reconnect_timeout: Seconds to wait for device to reappear.

        Returns:
            New tty device path after reconnection.

        Raises:
            ValueError: If name is invalid.
            TimeoutError: If device doesn't reappear.
        """
        if not name or len(name) > NAME_MAX_LEN:
            raise ValueError(f"Name must be 1-{NAME_MAX_LEN} ASCII characters")
        name_bytes = name.encode("ascii")

        # Send command: 0xAA <len> <name>
        cmd = bytes([CMD_SET_NAME, len(name_bytes)]) + name_bytes
        self._serial.write(cmd)
        self._serial.flush()

        # Device will reboot — close our end
        old_port = self.port
        try:
            self._serial.close()
        except Exception:
            pass

        # Wait for old device to disappear
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if not os.path.exists(old_port):
                break
            time.sleep(0.2)

        # Wait for new device to appear
        deadline = time.monotonic() + reconnect_timeout
        while time.monotonic() < deadline:
            devices = find_devices()
            if devices:
                new_port, new_name = devices[0]
                self.port = new_port
                self._serial = serial.Serial(new_port, baudrate=9600, timeout=1)
                return new_port
            time.sleep(0.5)

        raise TimeoutError(
            f"Device did not reappear within {reconnect_timeout}s"
        )
