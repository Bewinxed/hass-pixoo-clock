<p align="center">
  <img src="banner.png" width="256" alt="Pixoo Adaptive Clock" />
</p>

<h1 align="center">Pixoo Adaptive Clock</h1>

<p align="center">
  A Home Assistant custom integration that renders a pixel-perfect adaptive clock on Divoom Pixoo displays.
  <br/>
  Pairs with <a href="https://github.com/basnijholt/adaptive-lighting">Adaptive Lighting</a> to shift clock color temperature throughout the day.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS" /></a>
  <a href="https://github.com/Bewinxed/hass-pixoo-clock/releases"><img src="https://img.shields.io/github/v/release/Bewinxed/hass-pixoo-clock" alt="Release" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Bewinxed/hass-pixoo-clock" alt="License" /></a>
</p>

---

## What it does

Exposes your Divoom Pixoo as a **light entity** in Home Assistant. When [Adaptive Lighting](https://github.com/basnijholt/adaptive-lighting) (or anything else) changes the light's color temperature or brightness, this integration:

1. Converts the color temperature to RGB
2. Renders a 16x16 pixel clock image using a built-in 3x5 bitmap font
3. Pushes the image to your Pixoo via Bluetooth

The clock digits follow your circadian rhythm -- warm amber at night, cool white during the day.

### Features

- **Pixel-perfect 3x5 bitmap font** -- no external font files, hardcoded bitmaps
- **Progress border** -- 60 perimeter pixels fill clockwise, 1 per second
- **12-hour format** by default (configurable to 24h)
- **Adaptive color** -- responds to color_temp and RGB from any HA automation
- **Non-blocking** -- rendering runs in an executor, won't slow down HA
- **Duplicate frame skipping** -- only pushes to BT when something changes

### Display layout

```
+------------------+
| ooooooooooooo... |  <- Progress border (fills clockwise)
| o              . |
| o    ##   ##   . |  <- Hours (3x5 font, centered)
| o   ####  ##   . |
| o    ##   ##   . |
| o    ##   ##   . |
| o   #### ####  . |
| o              . |
| o      ::      . |  <- Colon separator
| o              . |
| o   #### ## ## . |  <- Minutes (3x5 font)
| o     ## ## ## . |
| o   #### ####  . |
| o     ##   ##  . |
| o   ####   ##  . |
| ................. |  <- Progress border
+------------------+
  o = border lit  . = border dim  # = digit
```

## Prerequisites

- [hass-divoom](https://github.com/d03n3rfr1tz3/hass-divoom) installed and configured with your Pixoo paired via Bluetooth
- A working `notify.divoom_device` service (test it in Developer Tools > Actions first)

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant UI
2. Go to **Integrations** > three-dot menu > **Custom repositories**
3. Add `https://github.com/Bewinxed/hass-pixoo-clock` with category **Integration**
4. Click **Install**
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/pixoo_clock` folder to your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

Add to your `configuration.yaml`:

```yaml
light:
  - platform: pixoo_clock
    name: "Pixoo Clock"
    notify_service: "notify.divoom_device"
    twelve_hour: true
```

| Option | Default | Description |
|--------|---------|-------------|
| `name` | `Pixoo Clock` | Entity name |
| `notify_service` | `notify.divoom_device` | The hass-divoom notify service to use |
| `twelve_hour` | `true` | Use 12-hour format (`false` for 24-hour) |

## Usage with Adaptive Lighting

1. Install [Adaptive Lighting](https://github.com/basnijholt/adaptive-lighting) via HACS
2. Go to **Settings > Devices & Services > Adaptive Lighting > Configure**
3. Add `light.pixoo_clock` (or whatever you named it) to the controlled lights
4. Done -- the clock color now follows your circadian schedule

You can also control it manually:

```yaml
# Set to warm amber
service: light.turn_on
target:
  entity_id: light.pixoo_clock
data:
  color_temp_kelvin: 2700
  brightness: 200

# Set to cool white
service: light.turn_on
target:
  entity_id: light.pixoo_clock
data:
  color_temp_kelvin: 5500
  brightness: 255

# Set to any RGB color
service: light.turn_on
target:
  entity_id: light.pixoo_clock
data:
  rgb_color: [255, 0, 128]

# Turn off the display
service: light.turn_off
target:
  entity_id: light.pixoo_clock
```

## Compatible devices

Tested with the original **Divoom Pixoo** (16x16, Bluetooth Classic). Should work with any 16x16 Divoom display supported by [hass-divoom](https://github.com/d03n3rfr1tz3/hass-divoom).

Larger displays (Pixoo-64, Pixoo-Max) will work but the clock will only use a 16x16 area. PRs welcome for multi-resolution support.

## How it works

The integration creates a standard Home Assistant `light` entity that supports `color_temp` and `rgb` color modes. Every second, it:

1. Checks if the time or color has changed since the last frame
2. If yes, renders a new 16x16 image using Pillow with the built-in bitmap font
3. Saves it as a GIF to `/config/pixelart/clock.gif`
4. Calls `notify.divoom_device` with `message: "image"` to push it to the Pixoo

The rendering runs in an executor thread so it never blocks the HA event loop.

## License

MIT
