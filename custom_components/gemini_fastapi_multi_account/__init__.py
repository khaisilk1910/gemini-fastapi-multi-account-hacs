"""The Gemini FastAPI Multi-Account integration."""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from openai import AsyncOpenAI
from .api import create_client
from .const import LOGGER
PLATFORMS = [Platform.AI_TASK, Platform.CONVERSATION]
type LocalAiConfigEntry = ConfigEntry[AsyncOpenAI]

async def async_setup_entry(hass: HomeAssistant, entry: LocalAiConfigEntry) -> bool:
    """Set up the integration without any network I/O during HA startup."""
    try:
        client = create_client(hass, dict(entry.data))
    except (KeyError, TypeError, ValueError) as err:
        raise ConfigEntryError(f"Invalid Gemini FastAPI server configuration: {err}") from err
    # OpenAI lazily builds platform headers; warm local-only metadata in the executor.
    _ = await hass.async_add_executor_job(client.platform_headers)
    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    LOGGER.debug("Gemini FastAPI Multi-Account loaded without startup network checks")
    return True

async def _async_update_listener(hass: HomeAssistant, entry: LocalAiConfigEntry) -> None:
    """Reload after config updates."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: LocalAiConfigEntry) -> bool:
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
