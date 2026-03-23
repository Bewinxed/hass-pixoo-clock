"""Constants for Pixoo Adaptive Clock."""
DOMAIN = "pixoo_clock"

CONF_NOTIFY_SERVICE = "notify_service"
CONF_TWELVE_HOUR = "twelve_hour"

DEFAULT_NAME = "Pixoo Clock"
DEFAULT_NOTIFY_SERVICE = "notify.divoom_device"
DEFAULT_TWELVE_HOUR = True

# 3x5 pixel font bitmaps for digits 0-9
# Each digit is a list of 5 rows, each row is 3 bits (MSB = leftmost pixel)
FONT_3x5 = {
    "0": [0b111, 0b101, 0b101, 0b101, 0b111],
    "1": [0b010, 0b110, 0b010, 0b010, 0b111],
    "2": [0b111, 0b001, 0b111, 0b100, 0b111],
    "3": [0b111, 0b001, 0b111, 0b001, 0b111],
    "4": [0b101, 0b101, 0b111, 0b001, 0b001],
    "5": [0b111, 0b100, 0b111, 0b001, 0b111],
    "6": [0b111, 0b100, 0b111, 0b101, 0b111],
    "7": [0b111, 0b001, 0b010, 0b010, 0b010],
    "8": [0b111, 0b101, 0b111, 0b101, 0b111],
    "9": [0b111, 0b101, 0b111, 0b001, 0b111],
}
