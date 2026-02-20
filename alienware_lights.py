#!/usr/bin/env python3
"""Alienware x15 R1 RGB light controller.

Usage:
  alienware-lights static RRGGBB           Set all lights to a solid color
  alienware-lights breathe RRGGBB [RRGGBB] Breathing effect with 1-3 colors
  alienware-lights morph RRGGBB RRGGBB ... Morph/cycle between 2-3 colors
  alienware-lights spectrum                Rainbow spectrum cycle
  alienware-lights wave                    Rainbow wave effect
  alienware-lights pulse RRGGBB            Pulsing single color
  alienware-lights off                     Turn all lights off

  Targets (optional, default: all):
    --keyboard   Only keyboard
    --tron       Only tron (ring + logos)
    --ring       Only ring
    --logos      Only logos

Examples:
  alienware-lights static FF1493
  alienware-lights breathe FF0000 00FF00 0000FF
  alienware-lights spectrum --keyboard
  alienware-lights off
"""
import os, fcntl, array, time, sys, subprocess, glob

HIDIOCSFEATURE = lambda l: 0xC0004806 | (l << 16)


def find_hidraw(vid, pid):
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*/device/uevent")):
        with open(path) as f:
            content = f.read()
        if vid in content and pid in content:
            return "/dev/" + path.split("/")[4]
    return None


def parse_color(s):
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


# ---------------------------------------------------------------------------
# Keyboard (Darfon, APIv5, feature reports with report ID 0xCC)
# ---------------------------------------------------------------------------

class Keyboard:
    def __init__(self):
        self.dev = find_hidraw("0D62", "BABC")
        self.fd = None

    def open(self):
        if not self.dev:
            print("Warning: keyboard not found", file=sys.stderr)
            return False
        self.fd = os.open(self.dev, os.O_RDWR | os.O_NONBLOCK)
        return True

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self._rebind()

    def _send(self, data):
        pkt = bytes([0xCC] + data + [0] * (64 - 1 - len(data)))
        buf = array.array('B', pkt)
        fcntl.ioctl(self.fd, HIDIOCSFEATURE(64), buf)

    def _rebind(self):
        if not self.dev:
            return
        uevent = "/sys/class/hidraw/" + self.dev.split("/")[-1] + "/device/uevent"
        phys = None
        try:
            with open(uevent) as f:
                for line in f:
                    if line.startswith("HID_PHYS="):
                        phys = line.strip().split("=", 1)[1].split("/")[0]
                        break
        except FileNotFoundError:
            return
        if phys:
            try:
                with open("/sys/bus/usb/drivers/usbhid/unbind", "w") as f:
                    f.write(phys)
                time.sleep(0.2)
                with open("/sys/bus/usb/drivers/usbhid/bind", "w") as f:
                    f.write(phys)
            except PermissionError:
                subprocess.run(
                    ["pkexec", "bash", "-c",
                     f'echo "{phys}" > /sys/bus/usb/drivers/usbhid/unbind; '
                     f'sleep 0.2; '
                     f'echo "{phys}" > /sys/bus/usb/drivers/usbhid/bind'],
                    check=False, capture_output=True)

    def _reset(self):
        self._send([0x94])
        time.sleep(0.05)

    def _commit(self):
        self._send([0x8b, 0x01, 0xFF])

    def _set_all_keys(self, r, g, b):
        for i in range(0, 0x88, 15):
            keys = list(range(i, min(i + 15, 0x88)))
            data = [0x8c, 0x02, 0x00]
            for k in keys:
                data += [k + 1, r, g, b]
            self._send(data)
            time.sleep(0.01)
        self._send([0x8c, 0x13])
        time.sleep(0.01)

    def _disable_effect(self):
        self._send([0x80, 0x01, 0xFE, 0x00, 0x00, 0x01, 0x01, 0x01])
        time.sleep(0.05)

    def _global_effect(self, eff_type, tempo, colors):
        data = [0x80, eff_type, tempo, 0x00, 0x00, 0x01, 0x01, 0x01]
        data.append(len(colors) - 1)  # nc-1
        for r, g, b in colors:
            data += [r, g, b]
        self._send(data)
        time.sleep(0.05)

    def static(self, r, g, b):
        self._reset()
        self._disable_effect()
        self._set_all_keys(r, g, b)
        self._commit()

    def breathe(self, colors):
        self._reset()
        self._disable_effect()
        self._global_effect(0x02, 0x07, colors)
        self._commit()

    def spectrum(self):
        self._reset()
        self._disable_effect()
        # Spectrum = breathing through full rainbow
        colors = [(0xFF, 0, 0), (0, 0xFF, 0), (0, 0, 0xFF)]
        self._global_effect(0x02, 0x05, colors)
        self._commit()

    def wave(self):
        self._reset()
        self._disable_effect()
        colors = [(0xFF, 0, 0), (0, 0xFF, 0), (0, 0, 0xFF)]
        self._global_effect(0x03, 0x05, colors)
        self._commit()

    def pulse(self, r, g, b):
        self._reset()
        self._disable_effect()
        self._global_effect(0x08, 0x07, [(r, g, b)])
        self._commit()

    def morph(self, colors):
        self._reset()
        self._disable_effect()
        self._global_effect(0x02, 0x05, colors)
        self._commit()

    def off(self):
        self.static(0, 0, 0)


# ---------------------------------------------------------------------------
# Tron lights (AW-ELC, APIv4, output reports, no report ID)
# ---------------------------------------------------------------------------

class Tron:
    RING_ZONES = list(range(10, 20))
    LOGO_ZONES = [0, 1]
    POWER_STATES = [0x5b, 0x5c, 0x5d, 0x5e, 0x5f, 0x60]

    MORPH_EFFECT = 0x02
    COLOR_EFFECT = 0x00
    COLOR_MODE = 0xD0
    MORPH_MODE = 0xCF
    PULSE_MODE = 0xDC

    def __init__(self):
        self.dev = find_hidraw("187C", "0550")
        self.fd = None

    def open(self):
        if not self.dev:
            print("Warning: AW-ELC not found", file=sys.stderr)
            return False
        self.fd = os.open(self.dev, os.O_RDWR | os.O_NONBLOCK)
        return True

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _send(self, data):
        pkt = bytes([0x03] + data + [0] * (33 - 1 - len(data)))
        os.write(self.fd, pkt)
        time.sleep(0.02)

    def _set_ring(self, actions, zones=None):
        """Set ring with user animation (0x21)."""
        if zones is None:
            zones = self.RING_ZONES
        self._send([0x21, 0x00, 0x04, 0x00, 0xFF])  # clear
        self._send([0x21, 0x00, 0x01, 0x00, 0xFF])  # start new
        self._send([0x23, 0x01, 0x00, len(zones)] + zones)  # select
        self._send([0x24] + actions)  # effect
        self._send([0x21, 0x00, 0x03, 0x00, 0xFF])  # play

    def _set_logos(self, actions, zones=None):
        """Set logos with power animation (0x22) across all power states."""
        if zones is None:
            zones = self.LOGO_ZONES
        # Commit any pending user animation first
        self._send([0x21, 0x00, 0x03, 0x00, 0xFF])
        time.sleep(0.05)
        for state in self.POWER_STATES:
            self._send([0x22, 0x00, 0x04, 0x00, state])  # remove
            self._send([0x22, 0x00, 0x01, 0x00, state])  # start new
            self._send([0x23, 0x01, 0x00, len(zones)] + zones)
            self._send([0x24] + actions)
            self._send([0x22, 0x00, 0x02, 0x00, state])  # save
        self._send([0x21, 0x00, 0x05, 0x00, 0xFF])  # play

    def _static_action(self, r, g, b):
        return [self.COLOR_EFFECT, 0x07, self.COLOR_MODE, 0x00, 0xFA, r, g, b]

    def _morph_actions(self, colors):
        """Build morph action data for up to 3 colors."""
        data = []
        for r, g, b in colors[:3]:
            data += [self.MORPH_EFFECT, 0x07, self.MORPH_MODE, 0x00, 0x64, r, g, b]
        return data

    def _pulse_action(self, r, g, b):
        return [0x01, 0x07, self.PULSE_MODE, 0x00, 0x64, r, g, b]

    def static(self, r, g, b, ring=True, logos=True):
        action = self._static_action(r, g, b)
        if ring:
            self._set_ring(action)
        if logos:
            self._set_logos(action)

    def breathe(self, colors, ring=True, logos=True):
        actions = self._morph_actions(colors)
        if ring:
            self._set_ring(actions)
        if logos:
            self._set_logos(actions)

    def morph(self, colors, ring=True, logos=True):
        self.breathe(colors, ring, logos)

    def spectrum(self, ring=True, logos=True):
        colors = [(0xFF, 0, 0), (0, 0xFF, 0), (0, 0, 0xFF)]
        self.breathe(colors, ring, logos)

    def pulse(self, r, g, b, ring=True, logos=True):
        action = self._pulse_action(r, g, b)
        if ring:
            self._set_ring(action)
        if logos:
            self._set_logos(action)

    def off(self, ring=True, logos=True):
        self.static(0, 0, 0, ring, logos)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    # Parse target flags
    do_keyboard = "--keyboard" in args
    do_tron = "--tron" in args
    do_ring = "--ring" in args
    do_logos = "--logos" in args
    args = [a for a in args if not a.startswith("--")]

    # Default: all targets
    if not any([do_keyboard, do_tron, do_ring, do_logos]):
        do_keyboard = do_tron = True

    do_ring_actual = do_tron or do_ring
    do_logos_actual = do_tron or do_logos

    cmd = args[0].lower()
    color_args = args[1:]

    kbd = Keyboard()
    tron = Tron()

    if do_keyboard:
        if not kbd.open():
            do_keyboard = False
    if do_ring_actual or do_logos_actual:
        if not tron.open():
            do_ring_actual = do_logos_actual = False

    try:
        if cmd == "static":
            r, g, b = parse_color(color_args[0]) if color_args else (0xFF, 0x14, 0x93)
            if do_keyboard:
                kbd.static(r, g, b)
            if do_ring_actual or do_logos_actual:
                tron.static(r, g, b, ring=do_ring_actual, logos=do_logos_actual)
            print(f"Static #{r:02X}{g:02X}{b:02X}")

        elif cmd == "breathe":
            colors = [parse_color(c) for c in color_args] if color_args else [(0xFF, 0, 0), (0, 0xFF, 0), (0, 0, 0xFF)]
            if do_keyboard:
                kbd.breathe(colors)
            if do_ring_actual or do_logos_actual:
                tron.breathe(colors, ring=do_ring_actual, logos=do_logos_actual)
            print(f"Breathing with {len(colors)} colors")

        elif cmd == "morph":
            colors = [parse_color(c) for c in color_args] if color_args else [(0xFF, 0, 0), (0, 0xFF, 0), (0, 0, 0xFF)]
            if do_keyboard:
                kbd.morph(colors)
            if do_ring_actual or do_logos_actual:
                tron.morph(colors, ring=do_ring_actual, logos=do_logos_actual)
            print(f"Morphing with {len(colors)} colors")

        elif cmd == "spectrum":
            if do_keyboard:
                kbd.spectrum()
            if do_ring_actual or do_logos_actual:
                tron.spectrum(ring=do_ring_actual, logos=do_logos_actual)
            print("Spectrum cycle")

        elif cmd == "wave":
            if do_keyboard:
                kbd.wave()
            if do_ring_actual or do_logos_actual:
                tron.spectrum(ring=do_ring_actual, logos=do_logos_actual)
            print("Rainbow wave")

        elif cmd == "pulse":
            r, g, b = parse_color(color_args[0]) if color_args else (0xFF, 0x14, 0x93)
            if do_keyboard:
                kbd.pulse(r, g, b)
            if do_ring_actual or do_logos_actual:
                tron.pulse(r, g, b, ring=do_ring_actual, logos=do_logos_actual)
            print(f"Pulsing #{r:02X}{g:02X}{b:02X}")

        elif cmd == "off":
            if do_keyboard:
                kbd.off()
            if do_ring_actual or do_logos_actual:
                tron.off(ring=do_ring_actual, logos=do_logos_actual)
            print("Lights off")

        else:
            print(f"Unknown command: {cmd}", file=sys.stderr)
            print(__doc__)
            sys.exit(1)

    finally:
        if do_keyboard:
            kbd.close()
        tron.close()


if __name__ == "__main__":
    main()
