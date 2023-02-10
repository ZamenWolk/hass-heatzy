"""Climate sensors for Heatzy."""
from datetime import datetime, timedelta
import logging
from typing import Optional, Any, Mapping

from heatzypy.exception import HeatzyException
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HeatzyDataUpdateCoordinator
from .const import (
    CFT_TEMP_H,
    CFT_TEMP_L,
    CONF_ALIAS,
    CONF_ATTR,
    CONF_MODE,
    CONF_MODEL,
    CONF_ON_OFF,
    CONF_PRODUCT_KEY,
    CONF_VERSION,
    CUR_TEMP_H,
    CUR_TEMP_L,
    DOMAIN,
    ECO_TEMP_H,
    ECO_TEMP_L,
    ELEC_PRO_SOC,
    GLOW,
    PILOTEV1,
    PILOTEV2,
    CONF_ATTRS, CONF_TIMER, PACKAGE_NAME,
)

MODE_LIST = [HVACMode.HEAT, HVACMode.OFF]
MODE_LIST_V2 = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
PRESET_LIST = [PRESET_NONE, PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

_LOGGER = logging.getLogger(PACKAGE_NAME)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Load all Heatzy devices."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for unique_id, device in coordinator.data.items():
        product_key = device.get(CONF_PRODUCT_KEY)
        if product_key in PILOTEV1:
            entities.append(HeatzyPiloteV1Thermostat(coordinator, unique_id))
        elif product_key in PILOTEV2 or product_key in ELEC_PRO_SOC:
            entities.append(HeatzyPiloteV2Thermostat(coordinator, unique_id))
        elif product_key in GLOW:
            entities.append(Glowv1Thermostat(coordinator, unique_id))
    async_add_entities(entities)


class HeatzyThermostat(CoordinatorEntity[HeatzyDataUpdateCoordinator], ClimateEntity):
    """Heatzy climate."""

    _attr_hvac_modes = MODE_LIST
    _attr_preset_modes = PRESET_LIST
    _attr_supported_features = ClimateEntityFeature.PRESET_MODE
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_has_entity_name = True

    def __init__(self, coordinator: HeatzyDataUpdateCoordinator, unique_id):
        """Init."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_name = "Thermostat"

    @property
    def device_info(self):
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.coordinator.data[self.unique_id][CONF_ALIAS],
            manufacturer=DOMAIN,
            sw_version=self.coordinator.data[self.unique_id].get(CONF_VERSION),
            model=self.coordinator.data[self.unique_id].get(CONF_MODEL),
        )

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self.preset_mode == PRESET_NONE:
            return HVACMode.OFF
        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        """Turn device on."""
        await self.async_set_preset_mode(PRESET_COMFORT)

    async def async_turn_off(self) -> None:
        """Turn device off."""
        await self.async_set_preset_mode(PRESET_NONE)


class HeatzyPiloteV1Thermostat(HeatzyThermostat):
    """Heaty Pilote v1."""

    HEATZY_TO_HA_STATE = {
        "\u8212\u9002": PRESET_COMFORT,
        "\u7ecf\u6d4e": PRESET_ECO,
        "\u89e3\u51bb": PRESET_AWAY,
        "\u505c\u6b62": PRESET_NONE,
    }
    HA_TO_HEATZY_STATE = {
        PRESET_COMFORT: [1, 1, 0],
        PRESET_ECO: [1, 1, 1],
        PRESET_AWAY: [1, 1, 2],
        PRESET_NONE: [1, 1, 3],
    }

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        return self.HEATZY_TO_HA_STATE.get(
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CONF_MODE)
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        try:
            await self.coordinator.async_control_device(
                self.unique_id,
                {"raw": self.HA_TO_HEATZY_STATE.get(preset_mode)},
            )
            await self.coordinator.async_request_refresh()
        except HeatzyException as error:
            _LOGGER.error("Set preset mode (%s) %s (%s)", preset_mode, error, self.name)


class HeatzyPiloteV2Thermostat(HeatzyThermostat):
    """Heaty Pilote v2."""

    _attr_hvac_modes = MODE_LIST_V2
    _attr_supported_features = HeatzyThermostat._attr_supported_features | ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 0
    _attr_max_temp = 21
    _attr_target_temperature_step = 1

    @property
    def _device_name(self):
        return self.coordinator.data[self.unique_id][CONF_ALIAS]

    # spell-checker:disable
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
    # spell-checker:enable

    PRESET_TO_TEMP = {
        PRESET_COMFORT: 21,
        PRESET_ECO: 16,
        PRESET_AWAY: 7,
        PRESET_NONE: 0
    }

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        last_update = self.coordinator.get_last_updated_time(self.unique_id)
        return {
            "recent_update_by_homeassistant":
                (last_update - datetime.now()) < timedelta(seconds=5)
                if last_update is not None
                else False
        }


    @property
    def target_temperature(self) -> Optional[float]:
        return self.PRESET_TO_TEMP.get(self.preset_mode)

    async def async_set_temperature(self, **kwargs) -> None:
        _LOGGER.info(f"Setting temperature for {self._device_name}")
        curr_preset = PRESET_COMFORT
        temp = kwargs["temperature"]
        for pr in self.PRESET_TO_TEMP.items():
            if abs(pr[1] - temp) < abs(self.PRESET_TO_TEMP[curr_preset] - temp):
                curr_preset = pr[0]

        await self.async_set_preset_mode(curr_preset)

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self.auto_mode:
            return HVACMode.AUTO
        if self.preset_mode == PRESET_NONE:
            return HVACMode.OFF
        else:
            return HVACMode.HEAT

    @property
    def auto_mode(self):
        return self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CONF_TIMER) == 1

    async def async_set_auto_mode(self, auto_mode: bool):
        _LOGGER.info(f"Setting auto mode for {self._device_name}")
        await self.coordinator.async_control_device(
            self.unique_id,
            {CONF_ATTRS: {CONF_TIMER: 1 if auto_mode else 0}}
        )
        await self.coordinator.async_request_refresh()
        _LOGGER.info(f"Auto mode set for {self._device_name}")

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_set_auto_mode(False)
            await self.async_set_preset_mode(PRESET_NONE)
        else:
            if hvac_mode == HVACMode.HEAT:
                await self.async_set_auto_mode(False)
            elif hvac_mode == HVACMode.AUTO:
                await self.async_set_auto_mode(True)

            if self.preset_mode == PRESET_NONE or hvac_mode == HVACMode.AUTO:
                await self.async_set_preset_mode(self.get_programmed_preset_at_time())

    def get_programmed_preset_at_time(self):
        return self.coordinator.get_programmed_preset_at_date(self.unique_id, datetime.now())

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        return self.HEATZY_TO_HA_STATE.get(
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CONF_MODE)
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        _LOGGER.info(f"Setting preset mode for {self._device_name}")
        await self.coordinator.async_control_device(
            self.unique_id,
            {CONF_ATTRS: {CONF_MODE: self.HA_TO_HEATZY_STATE.get(preset_mode)}}
        )
        await self.coordinator.async_request_refresh()
        _LOGGER.info(f"Preset mode set for {self._device_name}")


class Glowv1Thermostat(HeatzyPiloteV2Thermostat):
    """Glow."""

    _attr_supported_features = SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE_RANGE

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        cur_tempH = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CUR_TEMP_H)
        )
        cur_tempL = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CUR_TEMP_L)
        )
        return (cur_tempL + (cur_tempH * 255)) / 10

    @property
    def target_temperature_high(self) -> float:
        """Return comfort temperature."""
        cft_tempH = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CFT_TEMP_H, 0)
        )
        cft_tempL = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CFT_TEMP_L, 0)
        )
        return (cft_tempL + (cft_tempH * 255)) / 10

    @property
    def target_temperature_low(self) -> float:
        """Return comfort temperature."""
        eco_tempH = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(ECO_TEMP_H, 0)
        )
        eco_tempL = (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(ECO_TEMP_L, 0)
        )
        return (eco_tempL + (eco_tempH * 255)) / 10

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temp_eco = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_cft = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if (temp_eco or temp_cft) is None:
            return

        b_temp_cft = int(temp_cft * 10)
        b_temp_eco = int(temp_eco * 10)

        self.coordinator.data[self.unique_id].get(CONF_ATTR, {})[
            ECO_TEMP_L
        ] = b_temp_eco
        self.coordinator.data[self.unique_id].get(CONF_ATTR, {})[
            CFT_TEMP_L
        ] = b_temp_cft

        try:
            await self.coordinator.async_control_device(
                self.unique_id,
                {
                    CONF_ATTRS: {
                        CFT_TEMP_L: b_temp_cft,
                        ECO_TEMP_L: b_temp_eco,
                    }
                },
            )
            await self.coordinator.async_request_refresh()
        except HeatzyException as error:
            _LOGGER.error("Error to set temperature: %s", error)

    async def async_turn_on(self):
        """Turn device on."""
        try:
            await self.coordinator.async_control_device(
                self.unique_id, {CONF_ATTRS: {CONF_ON_OFF: 1}}
            )
            await self.coordinator.async_request_refresh()
        except HeatzyException as error:
            _LOGGER.error("Error to turn on : %s", error)

    async def async_turn_off(self):
        """Turn device off."""
        try:
            await self.coordinator.async_control_device(
                self.unique_id, {CONF_ATTRS: {CONF_ON_OFF: 0}}
            )
            await self.coordinator.async_request_refresh()
        except HeatzyException as error:
            _LOGGER.error("Error to turn off : %s", error)

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if (
            self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CONF_ON_OFF)
            == 0
        ):
            return HVACMode.OFF
        return HVACMode.HEAT
