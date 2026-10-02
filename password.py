"""
LevelMate Pro "password" (write authorization) computation.

Reverse-engineered from StringUtils.getPassword() in the official app's
decompiled bytecode. The device requires this 4-byte value to be written to
the password characteristic (AA21) immediately before any "protected" write
- install orientation (AA24), RV width (AA16), RV length (AA15), measurement
units, road side, etc. Without it, those writes fail with
`BleakGATTProtocolErrorCode.INSUFFICIENT_AUTHORIZATION`.

It is NOT required for subscribing to or reading the live leveling data
(_side/_front/_temperature notifications) - only for writes.

The algorithm, exactly as found in the app:

    hex1   = int(device_name[5:7], 16)
    hex2   = int(device_name[9:],  16)
    minute = current_local_time.minute            (0-59)
    hour12 = current_local_time.hour % 12          (Java Calendar.HOUR is a
                                                     12-hour-clock field, 0-11)

    byte0 = (hex1 + minute + 82) & 0xFF
    byte1 =  minute & 0xFF
    byte2 = (hex2 + hour12 + 55) & 0xFF
    byte3 =  hour12 & 0xFF

    password = bytes([byte0, byte1, byte2, byte3])

`device_name` is the device's BLE-advertised local name (GAP name), read
once by the app at pairing time and reused afterwards
(`DeviceSettings.getDevice_name()`). This integration instead reads the
currently-advertised name live from Home Assistant's Bluetooth integration
each time a password is needed, which should be equivalent.

Because this is time-synced to the *minute*, the clock the device itself
uses internally must agree with Home Assistant's clock to within undefined
tolerance (the app always recomputes and rewrites this immediately before
each protected write, suggesting it may only be valid for a short window -
possibly just the current minute). If your Home Assistant clock is off, or
if your LevelMate Pro's name doesn't follow the expected format, writes will
keep failing with INSUFFICIENT_AUTHORIZATION even though reads/notifications
work fine.
"""
from __future__ import annotations

import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


class PasswordComputationError(Exception):
    """Raised when the device's advertised name doesn't match the expected format."""


def compute_password(device_name: str | None, now: datetime | None = None) -> bytes:
    if not device_name or len(device_name) < 9:
        raise PasswordComputationError(
            f"Device name {device_name!r} is missing or too short to derive a "
            "password from (need at least 9 characters, with hex digits at "
            "positions 5-6 and from position 9 onward)."
        )

    now = now or datetime.now()

    try:
        hex1 = int(device_name[5:7], 16)
        hex2 = int(device_name[9:], 16)
    except ValueError as exc:
        raise PasswordComputationError(
            f"Could not parse hex segments out of device name {device_name!r} "
            f"(expected hex digits at [5:7] and [9:]): {exc}"
        ) from exc

    minute = now.minute
    hour12 = now.hour % 12

    byte0 = (hex1 + minute + 82) & 0xFF
    byte1 = minute & 0xFF
    byte2 = (hex2 + hour12 + 55) & 0xFF
    byte3 = hour12 & 0xFF

    password = bytes([byte0, byte1, byte2, byte3])
    _LOGGER.debug(
        "Computed password %s from device_name=%r at %02d:%02d",
        password.hex(), device_name, now.hour, now.minute,
    )
    return password
