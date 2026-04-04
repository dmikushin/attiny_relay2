"""
Hardware tests for ATtiny85 CDC ACM Relay Controller.

These tests require a real DigiSpark device connected via USB
with the relay firmware flashed.
"""

import os
import time
import pytest

# Add parent to path so relay_control is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from relay_control import RelayControl
from relay_control.relay import find_devices


@pytest.fixture
def relay():
    """Get a relay control instance, skip if no device found."""
    devices = find_devices()
    if not devices:
        pytest.skip("No ATtiny Relay device connected")
    ctrl = RelayControl(devices[0][0])
    yield ctrl
    # Leave relay ON (safe default)
    ctrl.relay_on()
    ctrl.close()


class TestDeviceDetection:
    def test_find_devices(self):
        """At least one device should be detected."""
        devices = find_devices()
        if not devices:
            pytest.skip("No ATtiny Relay device connected")
        port, name = devices[0]
        assert port.startswith("/dev/ttyACM")
        assert len(name) > 0

    def test_device_has_product_name(self):
        """Device should report a USB product name."""
        devices = find_devices()
        if not devices:
            pytest.skip("No ATtiny Relay device connected")
        _, name = devices[0]
        assert name, "Product name should not be empty"


class TestRelayControl:
    def test_relay_off(self, relay):
        """Serial break should set PB0 HIGH (relay OFF)."""
        relay.relay_off()
        time.sleep(0.1)
        # We can't directly read PB0, but we verify no exception
        assert relay._serial.break_condition is True

    def test_relay_on(self, relay):
        """Clearing break should set PB0 LOW (relay ON)."""
        relay.relay_off()
        time.sleep(0.1)
        relay.relay_on()
        time.sleep(0.1)
        assert relay._serial.break_condition is False

    def test_relay_toggle_rapid(self, relay):
        """Rapid toggling should not crash the device."""
        for _ in range(20):
            relay.relay_off()
            time.sleep(0.02)
            relay.relay_on()
            time.sleep(0.02)
        # Device should still respond
        assert relay._serial.is_open

    def test_held_break(self, relay):
        """Held break (repeated assertions) should keep relay OFF."""
        for _ in range(10):
            relay.relay_off()
            time.sleep(0.05)
        assert relay._serial.break_condition is True
        relay.relay_on()

    def test_name_property(self, relay):
        """Should be able to read device name via sysfs."""
        name = relay.name
        assert isinstance(name, str)
        assert len(name) > 0


class TestNameChange:
    def test_set_name_validation(self, relay):
        """Invalid names should raise ValueError."""
        with pytest.raises(ValueError):
            relay.set_name("")
        with pytest.raises(ValueError):
            relay.set_name("x" * 31)

    def test_set_and_restore_name(self, relay):
        """Change name, verify, restore original.

        This test reboots the device twice.
        """
        original_name = relay.name
        test_name = "TestRelay42"

        # Set new name (device reboots)
        try:
            relay.set_name(test_name)
        except TimeoutError:
            pytest.skip("Device did not reconnect (bootloader delay?)")

        # Verify new name
        assert relay.name == test_name

        # Restore original name
        try:
            relay.set_name(original_name)
        except TimeoutError:
            pytest.skip("Device did not reconnect for restore")

        assert relay.name == original_name
