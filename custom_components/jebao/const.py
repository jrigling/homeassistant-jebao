"""Constants for the Jebao integration."""
from typing import Final

DOMAIN: Final = "jebao"

# Configuration
CONF_DEVICE_ID: Final = "device_id"
CONF_MODEL: Final = "model"
CONF_INTERFACES: Final = "interfaces"

# Defaults
DEFAULT_NAME: Final = "Jebao Pump"
DEFAULT_SCAN_INTERVAL: Final = 30  # seconds

# Models
MODEL_MDP20000: Final = "MDP-20000"
MODEL_MDP15000: Final = "MDP-15000"

# Models the user can pick in options. Discovery can't always tell them apart:
# MDP-15000s have been seen reporting the MDP-20000's product key (04D30Q34).
SELECTABLE_MODELS: Final = [MODEL_MDP20000, MODEL_MDP15000]
MODEL_MD44: Final = "MD-4.4"
