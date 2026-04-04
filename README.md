# ATtiny85 CDC ACM Relay Controller

USB CDC ACM device (ttyACM) on DigiSpark ATtiny85 for controlling an induction relay via serial break signal.

## Relay Logic

| PB0 State | Relay | Trigger |
|-----------|-------|---------|
| LOW | ON (conducting) | Normal state / break cleared |
| HIGH | OFF (open, NO) | Serial Break asserted |

## Custom USB Device Name

The USB product name is stored in EEPROM and can be changed at runtime.
Send the command `0xAA <length> <name bytes>` on the ttyACM data channel.
The device writes the name to EEPROM, reloads the USB descriptor, and re-enumerates — no reboot required.
The new name is visible in `lsusb`.

Default name: `ATtiny Relay`

## Build

Requires: `avr-gcc`, `micronucleus`

```
make            # build firmware
make flash      # flash via micronucleus (re-plug DigiSpark when prompted)
```

V-USB library is cloned automatically on first build.

## Python Library

Requires: `pyserial`

```python
from relay_control import RelayControl

with RelayControl() as r:
    r.relay_off()               # PB0 HIGH, relay OFF (serial break)
    r.relay_on()                # PB0 LOW, relay ON (break cleared)
    r.set_name("My Relay")      # change USB device name (auto-reconnects)
    print(r.name)               # read current USB product name
```

## Tests

```
make test       # runs pytest against real hardware
```
