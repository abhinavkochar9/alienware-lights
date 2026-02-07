# alienware-lights

Control RGB lights on the Alienware x15 R1 under Linux. No AWCC, no Wine, no kernel module — just direct HID writes.

Controls three light groups:
- **Keyboard** — per-key RGB via the Darfon controller (`0d62:babc`, APIv5 feature reports)
- **Tron ring** — 10 ring zones via the AW-ELC controller (`187c:0550`, APIv4 output reports)
- **Logos** — power button + AlienHead via power-state animations on the same AW-ELC device

## Supported Hardware

Tested on:
- Alienware x15 R1

May work on other Alienware models that use the same USB vendor/product IDs (`0d62:babc` for keyboard, `187c:0550` for tron/logos). Check `lsusb` to see if your hardware matches.

## Installation

```bash
git clone https://github.com/abhinavkochar9/alienware-lights.git
cd alienware-lights
pip install .
```

### udev rules (required for non-root access)

```bash
sudo cp udev/99-alienware-lights.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### systemd service (optional — set color at boot)

```bash
sudo cp systemd/alienware-lights.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable alienware-lights
```

Edit the service file to change the boot color (default: `FF1493` / deep pink).

## Usage

```
alienware-lights <command> [colors...] [--target]
```

### Commands

| Command | Description |
|---------|-------------|
| `static RRGGBB` | Solid color |
| `breathe RRGGBB [RRGGBB ...]` | Breathing effect (1-3 colors) |
| `morph RRGGBB RRGGBB [...]` | Morph/cycle between 2-3 colors |
| `spectrum` | Rainbow spectrum cycle |
| `wave` | Rainbow wave effect (keyboard only) |
| `pulse RRGGBB` | Pulsing single color |
| `off` | Turn all lights off |

### Targets

| Flag | Description |
|------|-------------|
| *(none)* | All lights (default) |
| `--keyboard` | Keyboard only |
| `--tron` | Ring + logos |
| `--ring` | Ring only |
| `--logos` | Logos only |

### Examples

```bash
# Solid deep pink everywhere
alienware-lights static FF1493

# Breathe through red, green, blue
alienware-lights breathe FF0000 00FF00 0000FF

# Spectrum cycle on keyboard only
alienware-lights spectrum --keyboard

# Turn off tron lights, leave keyboard alone
alienware-lights off --tron

# Pulse cyan
alienware-lights pulse 00FFFF
```

## How It Works

The script talks directly to two USB HID devices via `/dev/hidraw*`:

**Keyboard (Darfon, APIv5):** Uses `ioctl` feature reports with report ID `0xCC`. Supports per-key color setting and global effects (breathe, wave, pulse). After writing, the USB device needs to be re-bound to restore normal keyboard function.

**Tron ring + logos (AW-ELC, APIv4):** Uses `write()` output reports. The ring uses "user animations" (command `0x21`), while logos use "power animations" (command `0x22`) that persist across power states (boot, sleep, shutdown, etc.).

No external dependencies — only Python stdlib (`os`, `fcntl`, `array`, `time`, `sys`, `subprocess`, `glob`).

## Credits

Protocol knowledge derived from:
- [T-Troll/alienfx-tools](https://github.com/T-Troll/alienfx-tools) — comprehensive AlienFX reverse engineering
- [cemkaya-mpi/Dell-G-Series-Controller](https://github.com/cemkaya-mpi/Dell-G-Series-Controller) — Dell/Alienware HID protocol research

## License

MIT
