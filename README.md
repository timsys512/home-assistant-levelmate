[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=timsys512&repository=home-assistant-levelmate&category=integration)

# Unofficial LevelMate Pro - Home Assistant Custom Integration

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

## Caveats - please read

- **Width and length are written to the device** (to match the official
  app's setup flow and because the device does store them).
- Writes to LevelMate device may not work due to password encryption. Make sure you
  configure the device with the Original LevelMate app prior to running this integration.
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
