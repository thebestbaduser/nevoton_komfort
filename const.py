"""Constants for the Nevoton Komfort integration."""

DOMAIN = "nevoton_komfort"

# Configuration
CONF_HOST = "host"
CONF_PASSWORD = "password"

# API endpoints
API_DEVICE_DESCRIPTION = "/get/m2m/deviceDescription"
API_GET_INPUTS = "/get/m2m/inputs"
API_GET_OUTPUTS = "/get/m2m/outputs"
API_SET_OUTPUTS = "/set/m2m/outputs"

# API parameters
PARAM_TYPE = "type"
PARAM_NUMBER = "number"
PARAM_HASH = "hash"
PARAM_SP_NAME = "sp_name"
PARAM_VALUE = "value"

# Channel types
TYPE_SPECIFIC = "specific"

# Specific parameters - Switches
PARAM_MAIN_POWER = "MainPower_switch"
PARAM_HEAT = "Heat_switch"
PARAM_HUMIDITY = "Humidity_switch"
PARAM_FAN = "Fan_switch"
PARAM_LIGHT = "Light_switch"

# Specific parameters - Timers
PARAM_TIMER_OFFSET_CHECKBOX = "TimerOffset_checkbox"
PARAM_TIMER_OFFSET_SET = "TimerOffset_time_SET"
PARAM_TIMER_OFFSET_REAL = "TimerOffset_time_REAL"
PARAM_TIME_HEAT_SET = "TimeHeat_SET"
PARAM_TIME_HEAT_REAL = "TimeHeat_REAL"

# Specific parameters - Sensors
PARAM_TEMPERATURE_SET = "Temperature_SET"
PARAM_TEMPERATURE_REAL = "Temperature_REAL"
PARAM_HUMIDITY_SET = "Humidity_SET"
PARAM_HUMIDITY_REAL = "Humidity_REAL"

# Specific parameters - Dimmers
PARAM_LIGHT_DIMMER = "Light_dimmer"

# Status
PARAM_STATUS = "Status"

# Limits
TEMP_MIN = 40
TEMP_MAX = 125
HUMIDITY_MIN = 10
HUMIDITY_MAX = 95
LIGHT_DIMMER_MAX = 6

# Update interval
DEFAULT_SCAN_INTERVAL = 10  # seconds
