"""Light platform for Pixoo Adaptive Clock.

Renders a pixel-perfect clock on 16x16 Divoom Pixoo displays.
Exposes as a light entity so Adaptive Lighting can drive color temperature
and brightness throughout the day.

Layout (16x16 grid):
    Row 0:      Progress border (top)
    Rows 1-6:   Hours (3x5 font, 12h format, centered)
    Row 7:      Gap
    Row 8:      Colon separator dots
    Row 9:      Gap
    Rows 10-14: Minutes (3x5 font, centered)
    Row 15:     Progress border (bottom)
    Col 0, 15:  Progress border (sides)

Border fills clockwise, 1 pixel per second (60 perimeter pixels = 60 seconds).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

from PIL import Image

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    PLATFORM_SCHEMA,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    CONF_NOTIFY_SERVICE,
    CONF_TWELVE_HOUR,
    DEFAULT_NAME,
    DEFAULT_NOTIFY_SERVICE,
    DEFAULT_TWELVE_HOUR,
    FONT_3x5,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(
            CONF_NOTIFY_SERVICE, default=DEFAULT_NOTIFY_SERVICE
        ): cv.string,
        vol.Optional(CONF_TWELVE_HOUR, default=DEFAULT_TWELVE_HOUR): cv.boolean,
    }
)


# ---------------------------------------------------------------------------
# Pixel rendering helpers
# ---------------------------------------------------------------------------

def _draw_digit(img: Image.Image, digit: int, x: int, y: int, color: tuple) -> None:
    """Draw a 3x5 digit bitmap onto *img* at pixel position (*x*, *y*)."""
    bitmap = FONT_3x5.get(str(digit))
    if bitmap is None:
        return
    for row_idx, row_bits in enumerate(bitmap):
        for col_idx in range(3):
            if row_bits & (1 << (2 - col_idx)):
                px, py = x + col_idx, y + row_idx
                if 0 <= px < 16 and 0 <= py < 16:
                    img.putpixel((px, py), color)


def _border_pixels() -> list[tuple[int, int]]:
    """Return the 60 perimeter pixels in clockwise order from top-left."""
    pixels: list[tuple[int, int]] = []
    # Top edge (L -> R)
    for x in range(16):
        pixels.append((x, 0))
    # Right edge (top+1 -> bottom-1)
    for y in range(1, 15):
        pixels.append((15, y))
    # Bottom edge (R -> L)
    for x in range(15, -1, -1):
        pixels.append((x, 15))
    # Left edge (bottom-1 -> top+1)
    for y in range(14, 0, -1):
        pixels.append((0, y))
    return pixels  # len == 60


BORDER_PIXELS = _border_pixels()


def render_clock(
    hour: int,
    minute: int,
    second: int,
    color: tuple[int, int, int],
    brightness_factor: float,
    twelve_hour: bool = True,
) -> Image.Image:
    """Render a 16x16 RGB clock image."""
    r = max(1, min(255, int(color[0] * brightness_factor)))
    g = max(1, min(255, int(color[1] * brightness_factor)))
    b = max(1, min(255, int(color[2] * brightness_factor)))
    fg = (r, g, b)
    border_dim = (max(1, r // 8), max(1, g // 8), max(1, b // 8))
    border_lit = (max(1, r // 2), max(1, g // 2), max(1, b // 2))
    sep_color = (max(1, r // 3), max(1, g // 3), max(1, b // 3))

    img = Image.new("RGB", (16, 16), (0, 0, 0))

    # --- Progress border ---
    for i, (px, py) in enumerate(BORDER_PIXELS):
        img.putpixel((px, py), border_lit if i < second else border_dim)

    # --- Hours ---
    if twelve_hour:
        display_hour = hour % 12 or 12
    else:
        display_hour = hour

    h_tens = display_hour // 10
    h_ones = display_hour % 10

    if h_tens >= 1:
        _draw_digit(img, h_tens, 4, 2, fg)
        _draw_digit(img, h_ones, 8, 2, fg)
    else:
        _draw_digit(img, h_ones, 6, 2, fg)

    # --- Separator ---
    img.putpixel((7, 8), sep_color)
    img.putpixel((8, 8), sep_color)

    # --- Minutes ---
    _draw_digit(img, minute // 10, 4, 10, fg)
    _draw_digit(img, minute % 10, 8, 10, fg)

    return img


# ---------------------------------------------------------------------------
# Color temperature conversion
# ---------------------------------------------------------------------------

def kelvin_to_rgb(kelvin: int) -> tuple[int, int, int]:
    """Convert color temperature (Kelvin) to an RGB tuple.

    Uses Tanner Helland's algorithm (attempt to match blackbody radiation).
    """
    temp = kelvin / 100.0

    # Red
    if temp <= 66:
        r = 255.0
    else:
        r = 329.698727446 * ((temp - 60) ** -0.1332047592)

    # Green
    if temp <= 66:
        g = 99.4708025861 * (max(temp, 2) ** 0.39036112843) - 161.1195681661
    else:
        g = 288.1221695283 * ((temp - 60) ** -0.0755148492)

    # Blue
    if temp >= 66:
        b = 255.0
    elif temp <= 19:
        b = 0.0
    else:
        b = 138.5177312231 * ((temp - 10) ** 0.50103842461) - 305.0447927307

    return (
        int(max(0, min(255, r))),
        int(max(0, min(255, g))),
        int(max(0, min(255, b))),
    )


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the Pixoo Clock light platform."""
    entity = PixooClockLight(
        hass=hass,
        name=config.get(CONF_NAME, DEFAULT_NAME),
        notify_service=config.get(CONF_NOTIFY_SERVICE, DEFAULT_NOTIFY_SERVICE),
        twelve_hour=config.get(CONF_TWELVE_HOUR, DEFAULT_TWELVE_HOUR),
    )
    async_add_entities([entity], True)

    async def _tick(_now):
        if entity.is_on:
            await entity._update_pixoo()

    async_track_time_interval(hass, _tick, timedelta(seconds=1))


# ---------------------------------------------------------------------------
# Light entity
# ---------------------------------------------------------------------------

class PixooClockLight(LightEntity):
    """A light entity that renders an adaptive pixel clock on a Divoom Pixoo."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        notify_service: str,
        twelve_hour: bool,
    ) -> None:
        self._hass = hass
        self._attr_name = name
        self._notify_service = notify_service
        self._twelve_hour = twelve_hour

        self._attr_unique_id = "pixoo_adaptive_clock"
        self._attr_is_on = False
        self._brightness = 200
        self._rgb: tuple[int, int, int] = (255, 170, 40)
        self._color_temp_kelvin = 2700

        self._last_second = -1
        self._last_color: tuple[int, int, int] | None = None
        self._sending = False
        self._clock_path = "/config/pixelart/clock.gif"
        os.makedirs("/config/pixelart", exist_ok=True)

    # -- Light properties --------------------------------------------------

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def color_mode(self) -> ColorMode:
        return ColorMode.COLOR_TEMP

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        return {ColorMode.COLOR_TEMP, ColorMode.RGB}

    @property
    def min_color_temp_kelvin(self) -> int:
        return 1000

    @property
    def max_color_temp_kelvin(self) -> int:
        return 6500

    @property
    def color_temp_kelvin(self) -> int:
        return self._color_temp_kelvin

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self._rgb

    # -- Commands ----------------------------------------------------------

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            self._rgb = kelvin_to_rgb(self._color_temp_kelvin)
        if ATTR_RGB_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGB_COLOR]

        # Force re-render
        self._last_color = None
        self._last_second = -1
        await self._update_pixoo()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        domain, service = self._notify_service.split(".", 1)
        await self._hass.services.async_call(domain, service, {"message": "off"})

    # -- Renderer ----------------------------------------------------------

    async def _update_pixoo(self) -> None:
        """Render the clock and push to the Pixoo."""
        if self._sending:
            return

        now = datetime.now()
        factor = self._brightness / 255.0
        current_color = (
            max(1, min(255, int(self._rgb[0] * factor))),
            max(1, min(255, int(self._rgb[1] * factor))),
            max(1, min(255, int(self._rgb[2] * factor))),
        )

        # Skip duplicate frames
        if now.second == self._last_second and current_color == self._last_color:
            return

        self._last_second = now.second
        self._last_color = current_color

        domain, service = self._notify_service.split(".", 1)
        if not self._hass.services.has_service(domain, service):
            return

        # Render off the event loop
        img = await self._hass.async_add_executor_job(
            render_clock,
            now.hour,
            now.minute,
            now.second,
            self._rgb,
            factor,
            self._twelve_hour,
        )
        await self._hass.async_add_executor_job(img.save, self._clock_path)

        # Push to the Pixoo via hass-divoom, skip if previous send still in flight
        self._sending = True
        try:
            await self._hass.services.async_call(
                domain, service, {"message": "image", "data": {"file": "clock.gif"}}
            )
        except Exception:
            _LOGGER.debug("Failed to send clock frame, will retry next tick")
        finally:
            self._sending = False
