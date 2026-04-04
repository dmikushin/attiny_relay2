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
The new name is visible in `lsusb`. Maximum length: 64 characters.

Default name: `ATtiny Relay`

## Firmware

Requires: `avr-gcc`, `micronucleus`

```
make            # build firmware
make flash      # flash via micronucleus (re-plug DigiSpark when prompted)
```

V-USB library is cloned automatically on first build.

## Python Installation

```
pip install .          # API library only
pip install .[mcp]     # API + MCP server
```

## Python API

```python
from relay_control import RelayControl

with RelayControl() as r:
    r.relay_off()               # PB0 HIGH, relay OFF (serial break)
    r.relay_on()                # PB0 LOW, relay ON (break cleared)
    r.set_name("My Relay")      # change USB device name (auto-reconnects)
    print(r.name)               # read current USB product name
```

## MCP Server

The package provides an MCP server for use with Claude Code via `mcp-compressor`.

### Setup

Add to `~/.claude.json` in the `mcpServers` section:

```json
{
  "mcpServers": {
    "usb-relay": {
      "command": "mcp-compressor",
      "args": ["-n", "usb-relay", "-c", "max", "usb-relay-mcp"]
    }
  }
}
```

Restart Claude Code after editing the config.

### Tools

| Tool | Description |
|------|-------------|
| `relay_list` | List connected relay devices (port, USB address, name) |
| `relay_on(device)` | Turn relay ON — accepts `/dev/ttyACMx` or USB address like `1-2` |
| `relay_off(device)` | Turn relay OFF |
| `relay_set_name(device, name)` | Change USB device name (1–64 ASCII chars) |

## Tests

```
make test       # runs pytest against real hardware
```
