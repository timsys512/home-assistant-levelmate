"""
Pure-Python decode/reconstruction logic for the LevelMate Pro, kept separate
from the Home Assistant plumbing so it can be unit-tested in isolation.

Everything here was reverse-engineered from the official app's decompiled
bytecode - see README.md for the full derivation and honesty notes about
what's 100% confirmed vs. still a working hypothesis.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from .const import INCHES_PER_RAW_COUNT


def decode_int16_le(raw: bytes) -> int | None:
    if len(raw) != 2:
        return None
    return struct.unpack("<h", raw)[0]


def decode_float32_le(raw: bytes) -> float | None:
    if len(raw) != 4:
        return None
    return struct.unpack("<f", raw)[0]


def celsius_to_fahrenheit(celsius: float) -> float:
    # Exact constants found in HomePresenter.onNotify.
    return celsius * 1.8 + 32


@dataclass
class CornerDeltas:
    """
    All four corner deltas, in inches. Each is how much MORE that corner
    needs raising to match the corner that's already highest (the
    "reference" corner, delta 0.0). Never negative.
    """

    reference_corner: str
    driver_front_in: float
    passenger_front_in: float
    driver_back_in: float
    passenger_back_in: float


# Corner relationships, from HomePresenter.showNumbers(): the corner sharing
# only the side-axis with the reference differs by |side|; the corner
# sharing only the front/back axis differs by |front|; the diagonal corner
# differs by |side| + |front|.
_PAIR_SIDE_AXIS = {
    "driver_front": "passenger_front",
    "passenger_front": "driver_front",
    "driver_back": "passenger_back",
    "passenger_back": "driver_back",
}
_PAIR_FRONT_AXIS = {
    "driver_front": "driver_back",
    "passenger_front": "passenger_back",
    "driver_back": "driver_front",
    "passenger_back": "passenger_front",
}
_DIAGONAL_OF = {
    "driver_front": "passenger_back",
    "passenger_back": "driver_front",
    "passenger_front": "driver_back",
    "driver_back": "passenger_front",
}


def reconstruct_corners(side_raw_int: int, front_raw_int: int) -> CornerDeltas:
    """
    Reconstructs the four corner deltas from the raw _side/_front integers,
    using the exact sign logic decompiled from HomePresenter's
    calculateHighestCorner()/highFront()/passengerLow()/getDisplayCorner():

      - highFront()    is true when _front < 0
      - passengerLow() is true when _side  > 0
      - reference corner (delta = 0):
            _front < 0 and _side > 0   -> driver_front
            _front < 0 and _side <= 0  -> passenger_front
            _front >= 0 and _side > 0  -> driver_back
            _front >= 0 and _side <= 0 -> passenger_back
      - driver = left, passenger = right, front = top, back = rear (the
        app's static VehicleCorner -> HomeCorner mapping)

    This assumes the device's install-orientation byte (CHAR_INSTALL_ORIENTATION)
    already matches how the unit is physically mounted - the firmware, not
    this formula, is what remaps raw sensor axes for a given orientation.
    """
    side_in = side_raw_int * INCHES_PER_RAW_COUNT
    front_in = front_raw_int * INCHES_PER_RAW_COUNT
    abs_side = abs(side_in)
    abs_front = abs(front_in)
    diagonal = abs_side + abs_front

    high_front = front_raw_int < 0
    side_positive = side_raw_int > 0

    if high_front and side_positive:
        reference = "driver_front"
    elif high_front and not side_positive:
        reference = "passenger_front"
    elif (not high_front) and side_positive:
        reference = "driver_back"
    else:
        reference = "passenger_back"

    corners = {
        "driver_front": None,
        "passenger_front": None,
        "driver_back": None,
        "passenger_back": None,
    }
    corners[reference] = 0.0
    corners[_PAIR_SIDE_AXIS[reference]] = round(abs_side, 4)
    corners[_PAIR_FRONT_AXIS[reference]] = round(abs_front, 4)
    corners[_DIAGONAL_OF[reference]] = round(diagonal, 4)

    return CornerDeltas(
        reference_corner=reference,
        driver_front_in=corners["driver_front"],
        passenger_front_in=corners["passenger_front"],
        driver_back_in=corners["driver_back"],
        passenger_back_in=corners["passenger_back"],
    )
