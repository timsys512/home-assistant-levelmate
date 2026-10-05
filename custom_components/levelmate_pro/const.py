"""Constants for the LevelMate Pro integration.

Every UUID, byte layout, and conversion formula below was reverse-engineered
directly from the official LogicBlue "LevelMate Pro" Android app's decompiled
bytecode (package com.logicblue.levelmateprov2) - there is no public protocol
document for this device. See README.md in this folder for the full writeup,
including which parts are 100% confirmed from the app's code vs. which are
still a best-effort working hypothesis that should be cross-checked against
your own device.
"""
from __future__ import annotations

DOMAIN = "levelmate_pro"

# --- BLE identifiers ---------------------------------------------------------

SERVICE_UUID = "0000aa10-0000-1000-8000-00805f9b34fb"

# Live tilt graphic only - NOT used for the corner numbers. Bleak needs the
# full 128-bit UUID string for every characteristic.
CHAR_PITCH_GRAPHIC = "0000aa11-0000-1000-8000-00805f9b34fb"
CHAR_ROLL_GRAPHIC = "0000aa12-0000-1000-8000-00805f9b34fb"

# The two REAL leveling measurements (signed int16 LE, 0.25 inch per count).
CHAR_SIDE = "0000aa13-0000-1000-8000-00805f9b34fb"
CHAR_FRONT = "0000aa14-0000-1000-8000-00805f9b34fb"

# RV length / width, in whole inches, signed int16 LE. Confirmed written to
# the device by the official app's "measure your RV" wizard - but NOT
# referenced anywhere in the corner-delta calculation we traced
# (HomePresenter.showNumbers/calculateHighestCorner/interpretValue). They may
# feed a different on-device feature (hitch assist, "dynamic site
# evaluation") that we have not reverse-engineered. Written here for parity
# with the official setup flow; don't expect them to change the 4 corner
# numbers.
CHAR_RV_LENGTH = "0000aa15-0000-1000-8000-00805f9b34fb"
CHAR_RV_WIDTH = "0000aa16-0000-1000-8000-00805f9b34fb"

CHAR_HITCH_POS = "0000aa17-0000-1000-8000-00805f9b34fb"
CHAR_BATTERY_LEVEL = "0000aa19-0000-1000-8000-00805f9b34fb"
CHAR_IDLE_TIME_UNTIL_SLEEP = "0000aa1a-0000-1000-8000-00805f9b34fb"
CHAR_WAKE_ON_MOTION = "0000aa1b-0000-1000-8000-00805f9b34fb"
CHAR_MEASUREMENT_UNITS = "0000aa1c-0000-1000-8000-00805f9b34fb"
CHAR_CONFIG_COMPLETE = "0000aa1d-0000-1000-8000-00805f9b34fb"
CHAR_LAST_HITCH_DATE = "0000aa1e-0000-1000-8000-00805f9b34fb"

# Only used by the separate trailer-hitch alignment feature - unrelated to
# the 4 corner numbers.
CHAR_HITCH_DELTA = "0000aa1f-0000-1000-8000-00805f9b34fb"

CHAR_TEMPERATURE = "0000aa20-0000-1000-8000-00805f9b34fb"
CHAR_PASSWORD = "0000aa21-0000-1000-8000-00805f9b34fb"

# Written to the device, 1 byte. See INSTALL_ORIENTATION_DEVICE_BYTE below
# for the exact value <-> meaning mapping (confirmed from
# InstallOrientationDevice.<clinit> and DeviceSettings.convertInstallORToDeviceOR).
CHAR_INSTALL_ORIENTATION = "0000aa24-0000-1000-8000-00805f9b34fb"

CHAR_RV_TYPE = "0000aa2b-0000-1000-8000-00805f9b34fb"
CHAR_DISPLAY_RESOLUTION = "0000aa2c-0000-1000-8000-00805f9b34fb"

# "Which side of the road you drive on" (left-hand drive vs right-hand
# drive). Confirmed to affect how "drivers side"/"passengers side" map to
# the device's absolute left/right orientation byte - see
# DeviceSettings.convertInstallORToDeviceOR in the README.
CHAR_ROAD_SIDE = "0000aa2d-0000-1000-8000-00805f9b34fb"

NOTIFY_CHARS = [CHAR_PITCH_GRAPHIC, CHAR_ROLL_GRAPHIC, CHAR_SIDE, CHAR_FRONT,
                CHAR_HITCH_DELTA, CHAR_TEMPERATURE]

# --- Scaling -----------------------------------------------------------------

INCHES_PER_RAW_COUNT = 0.25  # for CHAR_SIDE / CHAR_FRONT

# --- Install orientation ------------------------------------------------------
#
# The device's firmware - not the app - is what actually remaps the sensor's
# internal axes into "driver/passenger"+"front/rear" once you tell it (via
# CHAR_INSTALL_ORIENTATION) which way it's physically mounted. That's why the
# app's corner-delta formula (see levelmate_math.py) never has to adjust for
# orientation itself - it just trusts whatever the firmware already sent as
# _side/_front. This means: as long as this integration keeps the device's
# orientation byte in sync with what the user selects below, the same
# corner-delta formula is correct for all 4 mounting orientations.
#
# Confirmed device byte values (InstallOrientationDevice.<clinit>):
INSTALL_ORIENTATION_DEVICE_BYTE = {
    "faces_forward": 0,
    "faces_right": 1,
    "faces_rear": 2,
    "faces_left": 3,
}

# The app's user-facing "drivers side"/"passengers side" choices do NOT map
# to a fixed left/right - they depend on which side of the road you drive on
# (DeviceSettings.convertInstallORToDeviceOR). "front"/"rear" are unaffected.
ORIENTATION_CHOICES = [
    "faces_drivers_side",
    "faces_passengers_side",
    "faces_front",
    "faces_rear",
]

DRIVING_SIDE_CHOICES = ["left", "right"]  # left = LHD/US-style, right = RHD/UK-style


def install_orientation_to_device_byte(orientation: str, driving_side: str) -> int:
    """
    Converts the user-facing orientation choice + driving side into the
    actual byte to write to CHAR_INSTALL_ORIENTATION, exactly matching
    DeviceSettings.convertInstallORToDeviceOR() in the official app.
    """
    if orientation == "faces_front":
        return INSTALL_ORIENTATION_DEVICE_BYTE["faces_forward"]
    if orientation == "faces_rear":
        return INSTALL_ORIENTATION_DEVICE_BYTE["faces_rear"]
    if orientation == "faces_drivers_side":
        if driving_side == "left":
            return INSTALL_ORIENTATION_DEVICE_BYTE["faces_right"]
        return INSTALL_ORIENTATION_DEVICE_BYTE["faces_left"]
    if orientation == "faces_passengers_side":
        if driving_side == "left":
            return INSTALL_ORIENTATION_DEVICE_BYTE["faces_left"]
        return INSTALL_ORIENTATION_DEVICE_BYTE["faces_right"]
    # Fallback matches the app's own default branch.
    return INSTALL_ORIENTATION_DEVICE_BYTE["faces_forward"]


# --- Config entry keys --------------------------------------------------------

CONF_ADDRESS = "address"
CONF_WIDTH_INCHES = "width_inches"
CONF_LENGTH_INCHES = "length_inches"
CONF_ORIENTATION = "orientation"
CONF_DRIVING_SIDE = "driving_side"

DEFAULT_WIDTH_INCHES = 96
DEFAULT_LENGTH_INCHES = 360
DEFAULT_ORIENTATION = "faces_rear"
DEFAULT_DRIVING_SIDE = "left"
