"""Install or restore the fixed exposure settings hook."""

import struct

import _camera_io as pin


SITE = 0x86805A4C
LEGACY_CAVE = 0x86373400
CAVE = 0x86373800
HIT = 0x86373900
ORIGINAL = bytes.fromhex("95f8840a")
LEGACY_PATCH = pin.bw(SITE, LEGACY_CAVE)
PATCH = pin.bw(SITE, CAVE)
# Skip this one update while changing the second halfword. The rest of the
# publication proceeds and neither intermediate state decodes a mixed instruction.
STAGING = bytes.fromhex("01e0")


def write_checked(service, address, word):
    pin.w16(service, address, struct.unpack("<H", word)[0])
    if pin.rb(service, address, 2) != word:
        raise RuntimeError(f"Readback failed at {address:#010x}")


def replace_branch(service, desired, extra_versions=()):
    live = pin.rb(service, SITE, 4)
    if live == desired:
        return
    versions = (ORIGINAL, LEGACY_PATCH, PATCH, *extra_versions)
    known = {*versions, *(STAGING + version[2:] for version in versions)}
    if live not in known:
        raise RuntimeError(f"Unexpected instruction at {SITE:#010x}: {live.hex()}")
    if live[:2] == desired[:2]:
        write_checked(service, SITE + 2, desired[2:])
        return
    if live[:2] != STAGING:
        write_checked(service, SITE, STAGING)
    if live[2:] != desired[2:]:
        write_checked(service, SITE + 2, desired[2:])
    write_checked(service, SITE, desired[:2])
