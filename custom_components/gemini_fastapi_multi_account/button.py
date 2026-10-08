"""Reload button for Gemini FastAPI Multi-Account."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LocalAiConfigEntry
from .const import LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LocalAiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the reload button for a config entry."""
    async_add_entities([GeminiFastApiReloadButton(entry)])


class GeminiFastApiReloadButton(ButtonEntity):
    """Reload the owning Gemini FastAPI Multi-Account config entry."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_icon = "mdi:reload"
    _attr_translation_key = "reload_integration"

    def __init__(self, entry: LocalAiConfigEntry) -> None:
        """Initialize the reload button."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_reload_integration"

    async def async_press(self) -> None:
        """Schedule a safe config-entry reload without blocking this entity call."""
        if self._entry.disabled_by is not None:
            raise HomeAssistantError("This config entry is disabled and cannot be reloaded")
        if not self._entry.state.recoverable:
            raise HomeAssistantError(
                f"This config entry cannot be reloaded while it is {self._entry.state.value}"
            )

        LOGGER.info(
            "Reload button pressed: entry_id=%s title=%s state=%s",
            self._entry.entry_id,
            self._entry.title,
            self._entry.state.value,
        )
        self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
