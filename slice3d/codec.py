"""Fixed-point and bit-level primitives shared by embed/extract.

Vertex coordinates are floating point in the file, but LSB steganography needs a
stable integer representation. We scale a coordinate by ``SCALE`` (matching the
mesh writer's decimal ``PRECISION``) and round to an integer; the least
significant bit of that integer is the carrier. Because the mesh writer emits the
same number of decimals, ``write -> read -> to_fixed`` reproduces the integer
exactly, so an embedded bit survives a save/load round-trip.
"""

from __future__ import annotations

from typing import List

from slice3d.mesh import PRECISION

SCALE = 10 ** PRECISION

# Bits used for the length header prepended to every payload: an unsigned,
# big-endian byte count. 32 bits supports payloads up to 4 GiB.
HEADER_BITS = 32


# -- fixed-point ------------------------------------------------------------

def to_fixed(value: float) -> int:
    return int(round(value * SCALE))


def from_fixed(value: int) -> float:
    return value / SCALE


def get_lsb(n: int) -> int:
    return n % 2  # non-negative for negative n too (Python floor modulo)


def set_lsb(n: int, bit: int) -> int:
    return n - (n % 2) + bit


# -- bit packing ------------------------------------------------------------

def int_to_bits(value: int, width: int) -> List[int]:
    if value < 0:
        raise ValueError("int_to_bits expects a non-negative value")
    if value >= (1 << width):
        raise ValueError(f"value {value} does not fit in {width} bits")
    return [(value >> (width - 1 - i)) & 1 for i in range(width)]


def bits_to_int(bits: List[int]) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | (bit & 1)
    return value


def bytes_to_bits(data: bytes) -> List[int]:
    bits: List[int] = []
    for byte in data:
        bits.extend((byte >> (7 - i)) & 1 for i in range(8))
    return bits


def bits_to_bytes(bits: List[int]) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("bit count must be a multiple of 8")
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i : i + 8]:
            byte = (byte << 1) | (bit & 1)
        out.append(byte)
    return bytes(out)
