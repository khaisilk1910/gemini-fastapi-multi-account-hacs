"""The Gemini FastAPI Multi-Account integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryError, ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .api import GeminiFastApiClient, create_client
from .const import DOMAIN, LOGGER, SERVICE_RELOAD

PLATFORMS = [Platform.AI_TASK, Platform.BUTTON, Platform.CONVERSATION]
type LocalAiConfigEntry = ConfigEntry[GeminiFastApiClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up domain-wide services, including reload recovery for unloaded entries."""

    async def async_reload_service(call: ServiceCall) -> None:
        """Reload every enabled config entry for this integration."""
        entries = hass.config_entries.async_entries(
            DOMAIN,
            include_ignore=False,
            include_disabled=False,
        )
        if not entries:
            raise ServiceValidationError(
                "No enabled Gemini FastAPI Multi-Account config entries were found"
            )

        reloadable = [entry for entry in entries if entry.state.recoverable]
        if not reloadable:
            states = ", ".join(f"{entry.title}={entry.state.value}" for entry in entries)
            raise ServiceValidationError(
                "No Gemini FastAPI Multi-Account config entry can be reloaded right now"
                f" ({states})"
            )

        for entry in reloadable:
            LOGGER.info(
                "Scheduling Gemini FastAPI Multi-Account reload: entry_id=%s title=%s state=%s",
                entry.entry_id,
                entry.title,
                entry.state.value,
            )
            hass.config_entries.async_schedule_reload(entry.entry_id)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        async_reload_service,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LocalAiConfigEntry) -> bool:
    """Set up the integration without any network I/O during HA startup."""
    try:
        client = create_client(hass, dict(entry.data))
    except (KeyError, TypeError, ValueError) as err:
        raise ConfigEntryError(f"Invalid Gemini FastAPI server configuration: {err}") from err
    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    LOGGER.debug("Gemini FastAPI Multi-Account loaded without startup network checks")
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LocalAiConfigEntry) -> None:
    """Reload after config updates."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LocalAiConfigEntry) -> bool:
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
