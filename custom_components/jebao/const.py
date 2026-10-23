"""Constants for the Jebao integration."""
from typing import Final

DOMAIN: Final = "jebao"

# Configuration
CONF_DEVICE_ID: Final = "device_id"
CONF_MODEL: Final = "model"
CONF_INTERFACES: Final = "interfaces"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_SYNC_CLOCK: Final = "sync_clock"

# Defaults
DEFAULT_NAME: Final = "Jebao Pump"
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds
DEFAULT_SYNC_CLOCK: Final = True

# Models
MODEL_MDP20000: Final = "MDP-20000"
MODEL_MDP15000: Final = "MDP-15000"
MODEL_MDP5000: Final = "MDP-5000"
MODEL_MDP3500: Final = "MDP-3500"
MODEL_MDP2500: Final = "MDP-2500"

# Models the user can pick in options. Nothing on the network tells them apart: they
# report the same product key and datapoints, and the Jebao app doesn't know the
# model either (it shows the name the user gave the pump). The MDP-2500 (issue #1)
# is likely the same family but unconfirmed.
SELECTABLE_MODELS: Final = [
    MODEL_MDP20000,
    MODEL_MDP15000,
    MODEL_MDP5000,
    MODEL_MDP3500,
    MODEL_MDP2500,
]
MODEL_MD44: Final = "MD-4.4"

# Pump speed range in the app (0 stops the motor)
MIN_SPEED: Final = 30
MAX_SPEED: Final = 100

# Services
SERVICE_SET_SCHEDULE: Final = "set_schedule"
ATTR_SLOTS: Final = "slots"
ATTR_ENABLE: Final = "enable"
