"""Sensors for Heatzy."""
import logging

from heatzypy.exception import HeatzyException
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HeatzyDataUpdateCoordinator
from .const import CONF_ATTR, CONF_ATTRS, DOMAIN, CONF_LOCK, PACKAGE_NAME

_LOGGER = logging.getLogger(PACKAGE_NAME)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        LockSwitchEntity(coordinator, unique_id)
        for unique_id in coordinator.data.keys()
    ]
    async_add_entities(entities)


class LockSwitchEntity(CoordinatorEntity[HeatzyDataUpdateCoordinator], SwitchEntity):
    """Lock Switch."""

    entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, coordinator: HeatzyDataUpdateCoordinator, unique_id: str):
        """Initialize switch."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_name = "Lock switch"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.coordinator.data[self.unique_id].get(CONF_ATTR, {}).get(CONF_LOCK)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer=DOMAIN,
        )

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        try:
            await self.coordinator.async_control_device(
                self.unique_id, {CONF_ATTRS: {CONF_LOCK: 1}}
            )
        except Exception as error:
            _LOGGER.error("Error to lock pilot : %s", error)

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        try:
            await self.coordinator.async_control_device(
                self.unique_id, {CONF_ATTRS: {CONF_LOCK: 0}}
            )
        except Exception as error:
            _LOGGER.error("Error to lock pilot : %s", error)

        await self.coordinator.async_request_refresh()
