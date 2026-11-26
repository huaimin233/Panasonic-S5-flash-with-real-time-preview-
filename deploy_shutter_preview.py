#!/usr/bin/env python3
"""Install the DC-S5 preview and shutter sync through the settings sender."""

import argparse
from pathlib import Path
import time

import _camera_io as pin
import _settings_hook as iso


INSTALLER = 0x86373580
SETTINGS_CAVE = 0x86373D00
REQUEST = 0x86373B00
INSTALLER_BRANCH = pin.bw(iso.SITE, INSTALLER)
OLDER_INSTALLERS = tuple(pin.bw(iso.SITE, address)
                         for address in (0x86373A00, 0x86373600, 0x86373700))
INSTALLER_VERSIONS = (INSTALLER_BRANCH, *OLDER_INSTALLERS)
PIN_BRANCH = pin.bw(pin.TARGET, pin.CAVE)
PAYLOADS = Path(__file__).resolve().parent / "payloads"
PREVIEW_PAYLOAD = "payload_pin_packet.bin"


def read_payload(service, address, length):
    base = address & ~0x3FF
    offset = address - base
    return pin.get_s5svc().read_mem(service, base, offset + length)[offset:]


def stage_payload(service, address, name):
    payload = (PAYLOADS / name).read_bytes()
    limits = {pin.CAVE: 0xC00, SETTINGS_CAVE: 0x100, INSTALLER: 0x80}
    if not payload or len(payload) % 2 or len(payload) > limits[address]:
        raise RuntimeError(f"Invalid payload length for {name}")
    if read_payload(service, address, len(payload)) != payload:
        if not pin.wb_retry(service, address, payload):
            raise RuntimeError(f"Could not stage {name}")
        if read_payload(service, address, len(payload)) != payload:
            raise RuntimeError(f"Readback did not match for {name}")


def prepare(service):
    live = pin.rb(service, iso.SITE, 4)
    if live not in (iso.ORIGINAL, iso.PATCH, *INSTALLER_VERSIONS):
        raise RuntimeError(f"Unexpected settings instruction {live.hex()}")
    if pin.rb(service, pin.TARGET, 4) != pin.ORIG:
        raise RuntimeError("Expected original dispatcher instruction")
    if pin.rb(service, pin.GATE6, 4) != pin.GATE6_ORIG:
        raise RuntimeError("Expected original gate6 instruction")
    if pin.rb(service, 0x86410026, 8) != bytes.fromhex("08b5eff300800090"):
        raise RuntimeError("Unexpected instruction cache routine")
    pin.w16(service, REQUEST, 0)
    stage_payload(service, pin.CAVE, PREVIEW_PAYLOAD)
    if live != INSTALLER_BRANCH:
        stage_payload(service, SETTINGS_CAVE, "payload_exposure_preview.bin")
        stage_payload(service, INSTALLER, "payload_dispatcher_exposure.bin")
    for address in (pin.PREV, pin.ACTIVE, pin.ACTIVE + 2,
                    *pin.COUNTERS, *(a + 2 for a in pin.COUNTERS),
                    iso.HIT, iso.HIT + 2, iso.HIT + 4, iso.HIT + 8, iso.HIT + 10,
                    iso.HIT + 12, iso.HIT + 14):
        pin.w16(service, address, 0)
    iso.replace_branch(service, INSTALLER_BRANCH, INSTALLER_VERSIONS)
    pin.w16(service, REQUEST, 1)


def wait_for_dispatcher(service, desired, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = pin.r16(service, REQUEST)
        if state == 4:
            raise RuntimeError("Installer rejected the dispatcher instruction")
        if state == 3 and pin.rb(service, pin.TARGET, 4) == desired:
            return True
        time.sleep(0.15)
    return False


def remove_dispatcher(service):
    if pin.rb(service, pin.TARGET, 4) == pin.ORIG:
        return
    if pin.rb(service, iso.SITE, 4) not in INSTALLER_VERSIONS:
        raise RuntimeError("Expected the dispatcher installer in the settings sender")
    if pin.r16(service, pin.ACTIVE) & 255:
        raise RuntimeError("Exit Fn2 preview before switching payloads")
    pin.w16(service, REQUEST, 2)
    print("Removal armed. Change ISO to run the settings sender.", flush=True)
    if not wait_for_dispatcher(service, pin.ORIG):
        raise RuntimeError("The settings sender has not removed the dispatcher hook yet")


def report(service):
    request = pin.r16(service, REQUEST)
    dispatcher = pin.rb(service, pin.TARGET, 4)
    tick = pin.r16(service, pin.COUNTERS[0])
    print(f"Installer state={request}, dispatcher={dispatcher.hex()}, tick={tick}")
    print(f"Settings sender={pin.rb(service, iso.SITE, 4).hex()}")
    print(f"Preview={pin.r16(service, pin.ACTIVE) & 255}, "
          f"command={pin.r16(service, pin.CMD_A):04x}, "
          f"outgoing={pin.r16(service, 0x08AC7FAC) & 255:02x}, "
          f"en={pin.r16(service, 0x08B44356) & 255}")


def verify_running(service):
    tick = pin.r16(service, pin.COUNTERS[0])
    time.sleep(0.15)
    if pin.r16(service, pin.COUNTERS[0]) == tick:
        raise RuntimeError("Dispatcher bytes match, but the hook has not run")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("deploy", "replace", "rollback", "status"))
    args = parser.parse_args()
    service = pin.get_s5svc().Service(0.0)
    try:
        if args.action == "deploy" and pin.rb(service, pin.TARGET, 4) == PIN_BRANCH:
            expected = (PAYLOADS / PREVIEW_PAYLOAD).read_bytes()
            if (pin.rb(service, iso.SITE, 4) != INSTALLER_BRANCH
                    or read_payload(service, pin.CAVE, len(expected)) != expected):
                raise RuntimeError("A different preview is installed. Roll it back or cold-start first.")
            verify_running(service)
        elif args.action in ("deploy", "replace"):
            if args.action == "replace":
                remove_dispatcher(service)
            prepare(service)
            print("Installation armed. Change ISO to run the settings sender.", flush=True)
            if not wait_for_dispatcher(service, PIN_BRANCH):
                raise RuntimeError("Installation still pending. Change ISO, then check status.")
            verify_running(service)
        elif args.action == "rollback":
            remove_dispatcher(service)
            pin.w16(service, REQUEST, 0)
            iso.replace_branch(service, iso.ORIGINAL, INSTALLER_VERSIONS)
        report(service)
    finally:
        service.close()


if __name__ == "__main__":
    main()
