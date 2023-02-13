"""Heatzy platform configuration."""
import asyncio
import logging
import threading
from datetime import timedelta, datetime, time
from typing import Optional

import async_timeout
from heatzypy import HeatzyClient
from heatzypy.exception import AuthenticationFailed, HeatzyException
from homeassistant.components.climate import PRESET_COMFORT, PRESET_ECO, PRESET_AWAY, PRESET_NONE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DEBOUNCE_COOLDOWN, DOMAIN, PLATFORMS, CONF_ATTR, PACKAGE_NAME

_LOGGER = logging.getLogger(PACKAGE_NAME)
SCAN_INTERVAL = 60

_BITS_PER_STATE = 2

_BITS_TO_PRESET = {
    0: PRESET_COMFORT,
    1: PRESET_ECO,
    2: PRESET_AWAY,
    3: PRESET_NONE
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heatzy as config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = HeatzyDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

min_diff = timedelta(seconds=1.5)

class HeatzyDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to fetch datas."""

    _last_updated_time: dict[str, datetime] = {}

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Class to manage fetching Heatzy data API."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=DEBOUNCE_COOLDOWN, immediate=False
            ),
        )

        self._api = HeatzyClient(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            async_create_clientsession(hass),
        )

        self._lock = threading.Lock()

    async def async_control_device(self, device_id, payload):
        try:
            _LOGGER.info(f"Acquiring lock to control device {device_id}")
            with self._lock:
                last_update = self._last_updated_time.get(device_id)
                now = datetime.now()
                delta = now - last_update if last_update is not None else None
                if delta is not None and delta < min_diff:
                    _LOGGER.warning(f"Need to sleep for {(min_diff - delta).total_seconds()}s because "
                                    f"last update was too {delta.total_seconds()}s ago")
                    await asyncio.sleep((min_diff - delta).total_seconds())

                ret = await self._api.async_control_device(device_id, payload)
                self._last_updated_time[device_id] = datetime.now()
                _LOGGER.info(f"Releasing lock to control device {device_id}")
                return ret
        except Exception as error:
            _LOGGER.error("Error controling device: %s", error)

    def get_last_updated_time(self, device_id: str) -> Optional[datetime]:
        return self._last_updated_time.get(device_id)

    def get_programmed_preset_at_date(self, unique_id: str, date: datetime) -> Optional[str]:
        key = f"p{date.isoweekday()}_data{date.hour/2}"
        state_value = self.data.data[unique_id].get(CONF_ATTR, {}).get(key)

        if state_value is None:
            return None

        block_nb = ((date.hour % 2) >> 1) + int(date.minute < 30)
        return _BITS_TO_PRESET[(state_value << (_BITS_PER_STATE*block_nb)) % 2*_BITS_PER_STATE]

    async def _async_update_data(self) -> dict:
        """Update data."""
        try:
            async with async_timeout.timeout(API_TIMEOUT):
                data = await self._api.async_get_devices()
                return data
        except AuthenticationFailed as error:
            raise ConfigEntryAuthFailed from error
        except (HeatzyException, asyncio.TimeoutError) as error:
            raise UpdateFailed(error)
