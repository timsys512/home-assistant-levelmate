[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=timsayles1&repository=home-assistant-levelmate&category=integration)

# LevelMate Pro - Home Assistant Custom Integration

A Home Assistant custom component for the LogicBlue **LevelMate Pro** RV
leveling sensor. Connects directly over Bluetooth LE (no app, no cloud,
no internet required) and exposes:

- **Driver Front / Passenger Front / Driver Back / Passenger Back** corner
  sensors (inches) - how much *more* that corner needs raising to match the
  corner that's already highest.
- **Reference Corner** - which corner is currently the "already highest" one
  (the 0-inch datum the other three are measured against).
- **Temperature** sensor.
- Diagnostic **Raw Side Reading** / **Raw Front Reading** sensors (the two
  underlying axis values, in inches, before the corner math is applied).

During setup (and whenever you change options later) it also **writes**
your RV's width, length, and the LevelMate's physical mounting orientation
to the device itself - the same three settings the official app's setup
wizard asks for.

It also adds a **Bluetooth Connection** switch. Most BLE devices, including
the LevelMate Pro, only accept one connected app/hub at a time - so while
Home Assistant is connected, the official LevelMate phone app can't connect.
Turn this switch **off** to have Home Assistant release the connection (so
you can open the official app), then back **on** when you're done to resume
live sensor data here. This is intentionally not persisted across Home
Assistant restarts - every restart reconnects normally regardless of how you
left the switch.

## Why this exists / how it was built

LogicBlue never published a protocol spec for this device. Everything in
this integration - which Bluetooth characteristic is which, the byte
layout, the scaling, and the corner-reconstruction formula - was
reverse-engineered by decompiling the official Android app
(`com.logicblue.levelmateprov2`) and reading its Dalvik bytecode directly
(class `HomePresenter`, `LBBleRepo`, `DeviceSettings`, `ByteHelper`, and the
`InstallationOrientation`/`InstallOrientationDevice` enums). No guesswork
was used for the parts below marked "confirmed" - they're transcribed
straight from the app's own compiled logic.

### Characteristics (service `0000AA10`)

| UUID (short) | Field name in app | What it is | Status |
|---|---|---|---|
| `AA11` | `mDataPitch` | Raw bytes feeding the animated bubble-level graphic | Confirmed - **not** used for corner numbers |
| `AA12` | `mDataRoll` | Same - graphic only | Confirmed |
| `AA13` | `mDataSide` | Signed int16 LE, 0.25in/count - side-to-side delta | Confirmed from code; scale factor spot-checked against one known reading |
| `AA14` | `mDataFront` | Signed int16 LE, 0.25in/count - front/back delta | Confirmed from code; scale factor not yet independently cross-checked (see Caveats) |
| `AA15` | `mDataRVLength` | Signed int16 LE, whole inches | Confirmed write path; not referenced by the corner-delta formula |
| `AA16` | `mDataRVWidth` | Signed int16 LE, whole inches | Same as above |
| `AA1F` | `mDataHitchDelta` | Signed int16 LE | Used only by the separate trailer-hitch alignment feature |
| `AA20` | `mDataCurrentTemp` | float32 LE, Celsius | Confirmed (`F = C * 1.8 + 32`, exact constants in app) |
| `AA24` | `mDataInstallOrientation` | 1 byte, written by the app's setup wizard | Confirmed encoding (see below) |
| `AA2D` | `mDataRoadSideChar` | "Which side of the road you drive on" | Confirmed it affects orientation encoding; not written by this integration's data flow beyond the conversion below |

### The corner-reconstruction formula

From `HomePresenter.showNumbers()` / `calculateHighestCorner()` /
`highFront()` / `passengerLow()` (all confirmed by reading the bytecode):

- `highFront()` is true when `_front < 0`.
- `passengerLow()` is true when `_side > 0`.
- The corner that's already highest (shown as delta = **0**; every other
  corner is how much *more* it needs raising to match) is:
  - `_front < 0` and `_side > 0` &rarr; **driver front**
  - `_front < 0` and `_side <= 0` &rarr; **passenger front**
  - `_front >= 0` and `_side > 0` &rarr; **driver back**
  - `_front >= 0` and `_side <= 0` &rarr; **passenger back**
- The two corners adjacent to the reference corner (sharing one edge) =
  `|side|` and `|front|` respectively.
- The corner diagonally opposite = `|side| + |front|`.
- Driver = left, passenger = right, front = top, back = rear (the app's
  static `VehicleCorner` &rarr; `HomeCorner` mapping).

### Why orientation doesn't need software-side axis swapping

The LevelMate's **firmware itself** remaps which physical axis is "side" vs.
"front" based on the install-orientation byte you write to `AA24` - the
app's own corner formula never adjusts for orientation in software, because
it doesn't have to. That means this integration only has to keep `AA24` in
sync with what you select; it does not attempt to re-derive or flip signs
itself.

Confirmed byte encoding (`InstallOrientationDevice` class):

| Byte | Device-side meaning |
|---|---|
| 0 | Faces forward |
| 1 | Faces right |
| 2 | Faces rear |
| 3 | Faces left |

The app's user-facing "label faces driver's side / passenger's side"
options do **not** map to a fixed left/right byte - they depend on which
side of the road you drive on (`DeviceSettings.convertInstallORToDeviceOR`),
confirmed directly in the bytecode:

- Left-hand drive (e.g. US): driver's side &rarr; **faces right** (byte 1),
  passenger's side &rarr; **faces left** (byte 3).
- Right-hand drive (e.g. UK): driver's side &rarr; **faces left** (byte 3),
  passenger's side &rarr; **faces right** (byte 1).
- Front/rear are unaffected by driving side.

This integration asks for both your mounting orientation and your driving
side during setup, and performs this exact conversion.

## Write authorization ("password")

The device rejects protected writes (install orientation, RV width/length)
with `BleakGATTProtocolErrorCode.INSUFFICIENT_AUTHORIZATION` unless you
first write a specific 4-byte "password" to the `AA21` characteristic.
Reverse-engineered from `StringUtils.getPassword()` in the app:

```
hex1   = int(device_name[5:7], 16)
hex2   = int(device_name[9:],  16)
minute = current_local_time.minute
hour12 = current_local_time.hour % 12

byte0 = (hex1 + minute + 82) & 0xFF
byte1 =  minute & 0xFF
byte2 = (hex2 + hour12 + 55) & 0xFF
byte3 =  hour12 & 0xFF
```

`device_name` is the device's BLE-advertised local name. This integration
reads it live from Home Assistant's Bluetooth integration and recomputes a
fresh password immediately before each protected write (the app does the
same - the value is time-synced to the current minute/hour, so a stale one
won't be accepted).

**This part is confirmed from the app's code, but has two dependencies we
haven't been able to validate against a real device:**

1. **Your LevelMate Pro's advertised name must contain hex digits at
   character positions 5-6 and from position 9 to the end.** If it doesn't,
   you'll see a warning in the Home Assistant log naming the exact device
   name it saw - if that happens, please share that log line so the
   positions/algorithm can be corrected.
2. **Home Assistant's clock and the device's internal clock must agree to
   within whatever tolerance the firmware allows** (unknown - possibly just
   the current minute). If your Home Assistant host's clock is wrong, this
   will keep failing even with an otherwise-correct implementation.

If the password can't be computed or the write still fails, this
integration logs a warning and **continues running** - the four corner
sensors, temperature, and raw readings all come from notifications, which
do **not** require this password at all. Only the width/length/orientation
write step is skipped.

## Caveats - please read

- **Width and length are written to the device** (to match the official
  app's setup flow and because the device does store them), but based on
  everything we traced in `HomePresenter`, they do **not** currently feed
  into the corner-delta formula above. They may be used by some other
  on-device feature (hitch assist, "dynamic site evaluation") that wasn't
  reverse-engineered here. Don't expect changing them to change the four
  corner numbers.
- This is a from-scratch, unofficial integration, not affiliated with or
  supported by LogicBlue/LevelMate.

## Installation

1. Copy the `levelmate_pro` folder into your Home Assistant
   `config/custom_components/` directory (so you end up with
   `config/custom_components/levelmate_pro/__init__.py`, etc.).
2. Restart Home Assistant.
3. Make sure your LevelMate Pro is powered on and within range of an active
   Bluetooth adapter (or an ESPHome Bluetooth proxy) that Home Assistant's
   built-in Bluetooth integration can see.
4. Home Assistant should auto-discover it (Settings &rarr; Devices &
   Services &rarr; look for a "LevelMate Pro" discovery notification). If
   not, add it manually via Settings &rarr; Devices & Services &rarr; Add
   Integration &rarr; "LevelMate Pro".
5. During setup, enter your RV's width and length (inches), select the
   mounting orientation that matches your physical install (e.g. "Label
   faces rear"), and your driving side.
6. You can change any of these later via the integration's **Configure**
   button - this re-writes the new values to the device immediately.

## Requirements

- `bleak` (BLE client library)
- `bleak-retry-connector` (connection retry/caching helper used by many HA
  BLE integrations)

Both are listed in `manifest.json` and will be installed automatically by
Home Assistant.
