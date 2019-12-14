"""API for PiloteV2."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
)
from homeassistant.const import TEMP_CELSIUS

from .const import DOMAIN


HEATZY_TO_HA_STATE = {
    "cft": PRESET_COMFORT,
    "eco": PRESET_ECO,
    "fro": PRESET_AWAY,
    "stop": PRESET_NONE,
}

HA_TO_HEATZY_STATE = {
    PRESET_COMFORT: "cft",
    PRESET_ECO: "eco",
    PRESET_AWAY: "fro",
    PRESET_NONE: "stop",
}

MODE_LIST = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
PRESET_LIST = [PRESET_NONE, PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

_LOGGER = logging.getLogger(__name__)


class HeatzyPiloteV2Thermostat(ClimateDevice):
    """Heaty Pilote v2."""

    def __init__(self, api, device):
        """Init V2."""
        self._api = api
        self._heater = device
        self.update = self._update

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_PRESET_MODE

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._heater.get("did")

    @property
    def name(self):
        """Return a name."""
        return self._heater.get("dev_alias")

    @property
    def device_info(self):
        """Return the device info."""

        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": DOMAIN,
            "model": self._heater.get("product_name"),
            "sw_version": self._heater.get("wifi_soft_version"),
        }

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return MODE_LIST

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self.preset_mode == PRESET_NONE:
            return HVAC_MODE_OFF
        return HVAC_MODE_HEAT

    @property
    def preset_modes(self):
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        return PRESET_LIST

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        return HEATZY_TO_HA_STATE.get(self._heater.get("attr").get("mode"))

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        _LOGGER.debug(
            "Set PRESET MODE : {}".format(HA_TO_HEATZY_STATE.get(preset_mode))
        )
        await self._api.async_control_device(
            self.unique_id, {"attrs": {"mode": HA_TO_HEATZY_STATE.get(preset_mode)}}
        )

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new hvac mode."""
        _LOGGER.debug("Set HVAC MODE : {}".format(hvac_mode))
        if hvac_mode == HVAC_MODE_OFF:
            await self.async_turn_off()
        elif hvac_mode == HVAC_MODE_HEAT:
            await self.async_turn_on()

    async def async_turn_on(self):
        """Turn device on."""
        _LOGGER.debug("HVAC Turn On")
        await self.async_set_preset_mode(PRESET_COMFORT)

    async def async_turn_off(self):
        """Turn device off."""
        _LOGGER.debug("HVAC Turn off")
        await self.async_set_preset_mode(PRESET_NONE)

    async def async_update(self):
        """Get the latest state from the thermostat."""
        _LOGGER.debug("Update {}".format(self.name))
        self._device = await self._api.async_get_device(self.unique_id)