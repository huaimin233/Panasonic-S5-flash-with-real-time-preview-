#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Disassemble + emulate payload_pin.

  python check_pin.py payload_pin.bin

Models the settings publisher and checks that the original dispatcher prologue
and camera flash commands survive every preview transition.
"""
import struct
import argparse
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UcError
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5,
                               UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8,
                               UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP,
                               UC_ARM_REG_R10, UC_ARM_REG_R12, UC_ARM_REG_CPSR)

TARGET = 0x866B1244
ORIG = bytes.fromhex("2de9fc41")
RESUME = 0x866B1248
CAVE = 0x86370000
PUBLISH = 0x866B16B8

FN2 = 0x08AA82C2
SHUT = 0x08AA819C
PREV = 0x8F301014
ACTIVE = 0x8F301018
SLOT = 0x8F301008
CMD_A = 0x08CC1824
CMD_B = 0x08CB1B5C
EN_A = 0x08CA8182
EN_B = 0x08CB8936
SOURCE_EN = 0x08B44356
SOURCE_ISO = 0x08B4436C
PACKET_MODE = 0x08AC7FAC
SY_A = 0x08CA818C
SY_B = 0x08CB8940
TICK = 0x8F301020
N_EDGE = 0x8F301024
N_HALF = 0x8F301028
N_FULL = 0x8F30102C
N_PIN = 0x8F301030
N_ARM = 0x8F301034

RET = 0x8F380100
STACK = 0x8F380800
OFF = 0x0105


def bw(src, dst):
    delta = dst - (src + 4)
    S = (delta >> 24) & 1
    I1 = (delta >> 23) & 1
    I2 = (delta >> 22) & 1
    imm10 = (delta >> 12) & 0x3FF
    imm11 = (delta >> 1) & 0x7FF
    J1 = ((I1 ^ 1) & 1) ^ S
    J2 = ((I2 ^ 1) & 1) ^ S
    return struct.pack("<HH", 0xF000 | (S << 10) | imm10,
                       0x9000 | (J1 << 13) | (J2 << 11) | imm11)


def new_mu(hook, patch):
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    for base, size in ((CAVE & ~0xFFF, 0x4000), (TARGET & ~0xFFF, 0x2000),
                       (0x8F300000, 0x4000), (0x8F380000, 0x4000),
                       (0x08AA8000, 0x2000), (0x08CA8000, 0x2000),
                       (0x08B44000, 0x1000), (0x08AC7000, 0x3000),
                       (0x08CB0000, 0x10000), (0x08CC0000, 0x10000)):
        mu.mem_map(base, size)
    mu.mem_write(CAVE, hook)
    mu.mem_write(TARGET, patch)
    mu.mem_write(RESUME, struct.pack("<H", 0x4770))
    mu.mem_write(PUBLISH, struct.pack("<H", 0x4770))
    return mu


def r16(mu, a):
    return struct.unpack("<H", mu.mem_read(a, 2))[0]


def w16(mu, a, v):
    mu.mem_write(a, struct.pack("<H", v & 0xFFFF))


def apply(mu):
    phase = mu.mem_read(ACTIVE, 1)[0]
    mode = 5 if phase == 1 and not r16(mu, SHUT) else r16(mu, CMD_A) & 255
    off = mode == 5
    w16(mu, PACKET_MODE, mode)
    w16(mu, SOURCE_EN, int(not off))
    w16(mu, EN_A, 0 if off else 1)
    w16(mu, EN_B, 0 if off else 1)
    w16(mu, SY_A, 0x0D00 if off else 0x0800)
    w16(mu, SY_B, 0x0D00 if off else 0x0800)


def call(mu, fn2=0, shut=0):
    w16(mu, FN2, fn2)
    w16(mu, SHUT, shut)
    sent = (0x11111111, 0x22222222, 0x33333333, 0x44444444)
    high = (0x55555555, 0x66666666, 0x77777777, 0x88888888, 0x99999999)
    for reg, val in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), sent):
        mu.reg_write(reg, val)
    for reg, val in zip((UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                         UC_ARM_REG_R8), high):
        mu.reg_write(reg, val)
    mu.reg_write(UC_ARM_REG_LR, RET | 1)
    mu.reg_write(UC_ARM_REG_SP, STACK)
    mu.reg_write(UC_ARM_REG_PC, TARGET | 1)
    try:
        mu.emu_start(TARGET | 1, RESUME, count=1200)
    except UcError as e:
        raise AssertionError("emulation fault: %s (pc=0x%08X)" %
                             (e, mu.reg_read(UC_ARM_REG_PC)))
    got = [mu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
    if got != list(sent):
        raise AssertionError("r0-r3 clobbered: %s" % ["%08X" % x for x in got])
    goth = [mu.reg_read(r) for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                                     UC_ARM_REG_R7, UC_ARM_REG_R8)]
    if goth != list(high):
        raise AssertionError("r4-r8 clobbered: %s" % ["%08X" % x for x in goth])
    sp = mu.reg_read(UC_ARM_REG_SP)
    if sp != STACK - 32:
        raise AssertionError("SP after prologue = 0x%08X, expected 0x%08X" % (sp, STACK - 32))
    want = struct.pack("<8I", 0x33333333, 0x44444444, 0x55555555, 0x66666666,
                       0x77777777, 0x88888888, 0x99999999, RET | 1)
    if mu.mem_read(sp, 32) != want:
        raise AssertionError("prologue pushed wrong values: %s" % mu.mem_read(sp, 32).hex())


def fresh(mu, cmd=0x0106):
    mu.mem_write(0x8F300000, b"\x00" * 0x4000)
    mu.mem_write(0x8F380000, b"\x00" * 0x4000)
    w16(mu, CMD_A, cmd)
    w16(mu, CMD_B, cmd)
    w16(mu, EN_A, 1)
    w16(mu, EN_B, 1)
    w16(mu, SOURCE_EN, 1)
    w16(mu, SOURCE_ISO, 1000)
    w16(mu, PACKET_MODE, cmd & 255)
    w16(mu, SLOT, cmd)


def dump(mu):
    return (r16(mu, CMD_A), r16(mu, SLOT), mu.mem_read(ACTIVE, 1)[0], r16(mu, EN_A))


def run_steps(mu, steps):
    for s in steps:
        if s == "apply":
            apply(mu)
        elif s == "stray":
            w16(mu, CMD_A, OFF)
            w16(mu, CMD_B, OFF)
        else:
            call(mu, s[0], s[1])


def case(mu, name, cmd, steps, exp):
    fresh(mu, cmd)
    run_steps(mu, steps)
    got = dump(mu)
    ok = got == exp
    print("  %-44s cmd=%04X saved=%04X active=%d en=%04X  %s"
          % (name, got[0], got[1], got[2], got[3], "PASS" if ok else "FAIL exp %s" % (exp,)))
    return ok


def check_shutter_publish(mu):
    published = []

    def publish(uc, address, size, data):
        assert r16(uc, CMD_A) == r16(uc, CMD_B) == r16(uc, SLOT)
        published.append((uc.mem_read(ACTIVE, 1)[0], r16(uc, CMD_A)))
        apply(uc)
        for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3):
            uc.reg_write(reg, 0xDEADBEEF)

    mu.hook_add(UC_HOOK_CODE, publish, begin=PUBLISH, end=PUBLISH)
    for cmd in (0x0106, 0x010F):
        for first_press in (1, 0x100, 0x101):
            fresh(mu, cmd)
            published.clear()
            run_steps(mu, [(1, 0)] * 20 + [(0, 0)] * 14)
            assert dump(mu) == (cmd, cmd, 1, 0)
            call(mu)
            assert dump(mu) == (cmd, cmd, 2, 0)
            run_steps(mu, [(0, first_press), (0, 0), (0, 0x100)])
            assert published == [(1, cmd), (0, cmd)], (cmd, first_press, published)
    print("  Fn2 and first shutter pulse each publish once with the real mode intact  PASS")


def check_iso_refresh(mu):
    fresh(mu)
    run_steps(mu, [(1, 0)] + [(0, 0)] * 15 + ["apply", (0, 0)])
    assert dump(mu) == (0x0106, 0x0106, 2, 1)
    w16(mu, SOURCE_ISO, 1250)
    run_steps(mu, [(0, 0), (0, 0)])
    assert dump(mu) == (0x0106, 0x0106, 2, 0)
    assert r16(mu, PACKET_MODE) == 5
    run_steps(mu, ["apply"] + [(0, 0)] * 12)
    assert dump(mu) == (0x0106, 0x0106, 0, 1)
    print("  ISO change rearms preview. A normal update times out without rearming  PASS")


def check_settings_packet(payload):
    entry, resume = 0x86373D00, 0x86805A50
    packet, settings, context = 0x08AC7FA8, 0x08CC84F0, 0x08CA8078
    for phase, mode, before, after, aperture, speed, elapsed, shutter, expected in (
        (0, 6, 32, 33, 21, 1, None, 0, 6),
        (1, 6, 32, 32, 21, 1, None, 0, 5),
        (2, 6, 32, 32, 21, 1, None, 0, 6),
        (2, 6, 32, 33, 21, 1, None, 0, 5),
        (2, 6, 32, 32, 20, 1, None, 0, 5),
        (2, 6, 32, 32, 21, 2, None, 0, 5),
        (2, 6, 33, 33, 21, 1, 11, 0, 5),
        (2, 6, 33, 33, 21, 1, 12, 0, 6),
        (2, 6, 33, 33, 20, 2, 11, 1, 6),
        (2, 15, 32, 33, 21, 1, None, 0, 5),
        (2, 15, 32, 33, 21, 1, None, 0x100, 15),
    ):
        mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for address in (entry, resume, packet, settings, context, SHUT, CMD_A, ACTIVE, STACK):
            mu.mem_map(address & ~0xFFF, 0x1000)
        mu.mem_write(entry, payload)
        for address, value in ((CMD_A, mode), (ACTIVE, phase), (packet + 0x19, before),
                               (settings + 0x18a, after), (SHUT, shutter),
                               (0x08AA81A2, aperture), (0x08AA81A4, speed)):
            w16(mu, address, value)
        mu.mem_write(context + 0x484, struct.pack("<I", settings))
        mu.mem_write(TICK, struct.pack("<I", 100))
        mu.mem_write(0x86373908, struct.pack("<I", 0 if elapsed is None else 100 - elapsed))
        mu.mem_write(0x8637390C, struct.pack("<HH", 21, 1))
        registers = {UC_ARM_REG_R2: 21, UC_ARM_REG_R3: 31, UC_ARM_REG_R4: packet,
                     UC_ARM_REG_R5: 0x08CC0DA0, UC_ARM_REG_R10: context,
                     UC_ARM_REG_R12: 121, UC_ARM_REG_LR: RET | 1, UC_ARM_REG_SP: STACK}
        for reg, value in registers.items():
            mu.reg_write(reg, value)
        flags = mu.reg_read(UC_ARM_REG_CPSR) & 0xF8000000
        mu.emu_start(entry | 1, resume, count=140)
        assert mu.reg_read(UC_ARM_REG_R0) == expected
        assert all(mu.reg_read(reg) == value for reg, value in registers.items())
        assert mu.reg_read(UC_ARM_REG_CPSR) & 0xF8000000 == flags
    print("  Exposure adjustments preserve ambient preview. Shutter bypasses the override  PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    bundled = Path(__file__).resolve().parent / "payloads" / "payload_pin_packet.bin"
    parser.add_argument("payload", type=Path, nargs="?", default=bundled)
    path = parser.parse_args().payload
    hook = path.read_bytes()
    patch = bw(TARGET, CAVE)
    print("payload_pin: %d bytes, patch %s" % (len(hook), patch.hex()))
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    n = 0
    for ins in md.disasm(hook, CAVE):
        n += 1
    print("capstone decoded %d instructions" % n)
    assert any(hook[i:i + 4] == ORIG and hook[i + 4:i + 8] == bw(CAVE + i + 4, RESUME)
               for i in range(0, len(hook) - 7, 2)), "original prologue and return jump missing"
    print("tail ok\n")

    mu = new_mu(hook, patch)
    check_shutter_publish(mu)
    check_iso_refresh(mu)
    check_settings_packet(path.with_name("payload_exposure_preview.bin").read_bytes())
    ok = True
    ok &= case(mu, "idle keeps mode", 0x0106, [(0, 0), (0, 0)], (0x0106, 0x0106, 0, 1))
    ok &= case(mu, "press -> apply and release override", 0x0106,
               [(1, 0)] + [(0, 0)] * 15, (0x0106, 0x0106, 2, 0))
    ok &= case(mu, "press again closes", 0x0106,
               [(1, 0), "apply", (0, 0), (1, 0), "apply", (0, 0)], (0x0106, 0x0106, 0, 1))
    ok &= case(mu, "half-press arms flash", 0x0106,
               [(1, 0), "apply", (0, 1), "apply", (0, 0)], (0x0106, 0x0106, 0, 1))
    ok &= case(mu, "full-press arms flash", 0x0106,
               [(1, 0), "apply", (0, 0x100), "apply", (0, 0)], (0x0106, 0x0106, 0, 1))
    ok &= case(mu, "redeye preserved", 0x010F,
               [(1, 0), "apply", (0, 0x100), "apply", (0, 0)], (0x010F, 0x010F, 0, 1))
    ok &= case(mu, "firmware can turn flash off", 0x0106, ["stray", "apply", (0, 0)], (0x0105, 0x0106, 0, 0))

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
