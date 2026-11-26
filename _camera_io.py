"""USB service I/O used by the fixed DC-S5 preview deployer."""

from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import struct
import time

CAVE = 0x86370000
TARGET = 0x866B1244
ORIG = bytes.fromhex("2de9fc41")
GATE6 = 0x867833E6
GATE6_ORIG = bytes.fromhex("2de9f041")
CMD_A = 0x08CC1824
PREV = 0x8F301014
ACTIVE = 0x8F301018
COUNTERS = (0x8F301020, 0x8F301024, 0x8F301028, 0x8F30102C,
            0x8F301030, 0x8F301034)


@lru_cache(maxsize=1)
def get_s5svc():
    directory = Path(os.environ.get("LUMIX_S5SVC") or Path(__file__).resolve().parent)
    path = directory / "s5svc.py"
    if not path.is_file():
        raise SystemExit("s5svc.py not found. Restore the bundled file or set LUMIX_S5SVC to its directory.")
    spec = spec_from_file_location("s5svc", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    required = ("Service", "build_0x9b", "build_0x9c", "read_mem")
    missing = [name for name in required if not callable(getattr(module, name, None))]
    if missing:
        raise SystemExit(f"Incompatible s5svc.py: missing {', '.join(missing)}")
    return module


def bw(src, dst):
    delta = dst - (src + 4)
    sign = (delta >> 24) & 1
    i1 = (delta >> 23) & 1
    i2 = (delta >> 22) & 1
    imm10 = (delta >> 12) & 0x3FF
    imm11 = (delta >> 1) & 0x7FF
    j1 = ((i1 ^ 1) & 1) ^ sign
    j2 = ((i2 ^ 1) & 1) ^ sign
    return struct.pack("<HH", 0xF000 | (sign << 10) | imm10,
                       0x9000 | (j1 << 13) | (j2 << 11) | imm11)


def r16(svc, address):
    reply = svc.exchange(get_s5svc().build_0x9b(address))
    if len(reply) < 6 or reply[3] != 0x36:
        raise RuntimeError(f"Read failed at {address:#010x}: {reply.hex()}")
    return struct.unpack_from("<H", reply, 4)[0]


def w16(svc, address, value):
    svc.exchange_write(get_s5svc().build_0x9c(address, value & 0xFFFF))


def rb(svc, address, length):
    out = bytearray()
    for offset in range(0, length, 2):
        out += struct.pack("<H", r16(svc, address + offset))
    return bytes(out)


def wb_retry(svc, address, data, tries=5):
    for attempt in range(1, tries + 1):
        try:
            for offset in range(0, len(data), 2):
                w16(svc, address + offset, struct.unpack_from("<H", data, offset)[0])
            return True
        except Exception as error:
            print(f"RAM write attempt {attempt}/{tries} at {address:#010x}: {error}")
            time.sleep(0.4)
    return False
