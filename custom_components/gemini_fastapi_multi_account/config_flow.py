"""Config flow for Gemini FastAPI Multi-Account integration."""

from __future__ import annotations

import re

import probatio as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LLM_HASS_API,
    CONF_MODEL,
    CONF_NAME,
    CONF_PROMPT,
)
from homeassistant.core import callback
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TemplateSelector,
)

from .api import ApiClientError, create_client, normalize_base_url
from .model_selection import model_selector_options
from .const import (
    DOMAIN,
    LOGGER,
    MODEL_LIST_TIMEOUT,
    RECOMMENDED_CONVERSATION_OPTIONS,
    LocalAiConfigKey,
    LocalAiSubentryType,
)


class LocalAiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gemini FastAPI Multi-Account."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {
            LocalAiSubentryType.CONVERSATION: ConversationFlowHandler,
            LocalAiSubentryType.AI_TASK_DATA: AITaskDataFlowHandler,
        }

    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial config flow step."""
        LOGGER.debug("Config flow: step_user invoked")
        errors = {}
        if user_input is not None:
            user_input = user_input.copy()
            try:
                user_input[LocalAiConfigKey.BASE_URL] = normalize_base_url(
                    user_input[LocalAiConfigKey.BASE_URL]
                )
            except (KeyError, ValueError):
                errors["base"] = "invalid_url"
            else:
                self._async_abort_entries_match(user_input)
                LOGGER.debug(
                    "Validating Gemini FastAPI server at %s",
                    user_input[LocalAiConfigKey.BASE_URL],
                )
                try:
                    client = create_client(self.hass, user_input)
                    await client.list_models(timeout=MODEL_LIST_TIMEOUT)
                except ApiClientError as err:
                    LOGGER.debug("Gemini FastAPI validation failed: %s", err)
                    errors["base"] = (
                        "invalid_auth"
                        if err.status_code in (401, 403)
                        else "cannot_connect"
                    )
                except Exception:
                    LOGGER.exception("Unexpected exception while validating Gemini FastAPI")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=str(
                            user_input.get(
                                LocalAiConfigKey.SERVER_NAME,
                                "Gemini FastAPI Multi-Account",
                            )
                        ),
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        LocalAiConfigKey.SERVER_NAME,
                        default="Gemini FastAPI Multi-Account",
                    ): str,
                    vol.Required(LocalAiConfigKey.BASE_URL): str,
                    vol.Optional(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )


class LocalAiSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for Gemini FastAPI Multi-Account."""

    async def get_model_options(
        self, options: dict[str, object]
    ) -> tuple[list[SelectOptionDict], bool]:
        """Load live choices, or fall back without erasing the saved model.

        A failed or empty /v1/models endpoint must not leave the Home Assistant
        selector with zero entries, especially when reconfiguring an agent.
        Returns (selector options, has_live_models).
        """
        model_ids: list[str] = []
        try:
            client = self._get_entry().runtime_data
            model_ids = await client.list_models(timeout=MODEL_LIST_TIMEOUT)
        except ApiClientError as err:
            LOGGER.warning("Could not fetch Gemini FastAPI models: %s", err)
        except Exception:
            LOGGER.exception("Unexpected error retrieving Gemini FastAPI models")

        if not model_ids:
            LOGGER.warning(
                "Gemini FastAPI model list is empty/unavailable; showing fallback "
                "candidates. Check GET /v1/models and the gateway account status."
            )
        selected = options.get(CONF_MODEL)
        selected_model = str(selected) if selected is not None else None
        choices = model_selector_options(model_ids, selected_model)
        return [SelectOptionDict(**choice) for choice in choices], bool(model_ids)

    @staticmethod
    def strip_model_pathing(model_name: str) -> str:
        """Strip file path and .gguf extension from model name."""
        matches = re.search(r"([^/]*)\.gguf$", model_name.strip())
        return matches[1] if matches else model_name


class ConversationFlowHandler(LocalAiSubentryFlowHandler):
    """Handle subentry flow."""

    def get_llm_apis(self) -> list[SelectOptionDict]:
        """Return available LLM APIs as select options."""
        return [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]

    async def get_schema(self, options: dict[str, object] | None = None):
        """Return the configuration schema for conversation options."""
        if options is None:
            options = {}
        llm_apis = self.get_llm_apis()
        downloaded_models, has_live_models = await self.get_model_options(options)
        LOGGER.debug("Available model options: %s", downloaded_models)

        if raw_model := options.get(CONF_MODEL):
            default_model = str(raw_model)
        elif has_live_models:
            default_model = downloaded_models[0]["value"]
        else:
            # Do not default new agents to an unverified Auto alias while
            # /v1/models is offline. The user can still choose it explicitly.
            default_model = "gemini-flash"

        default_title = self.strip_model_pathing(default_model)
        default_name: str = f"{default_title} AI Agent"
        if raw_name := options.get(CONF_NAME):
            default_name = str(raw_name)

        return vol.Schema(
            {
                vol.Optional(
                    CONF_NAME,
                    default=default_name,
                ): str,
                vol.Required(
                    CONF_MODEL,
                    default=default_model,
                ): SelectSelector(
                    SelectSelectorConfig(options=downloaded_models, custom_value=True)
                ),
                vol.Optional(
                    CONF_PROMPT,
                    default=options.get(CONF_PROMPT, RECOMMENDED_CONVERSATION_OPTIONS[CONF_PROMPT]),
                ): TemplateSelector(),
                vol.Optional(
                    CONF_LLM_HASS_API,
                    default=options.get(
                        CONF_LLM_HASS_API,
                        RECOMMENDED_CONVERSATION_OPTIONS[CONF_LLM_HASS_API],
                    ),
                ): SelectSelector(SelectSelectorConfig(options=llm_apis, multiple=True)),
                vol.Optional(
                    LocalAiConfigKey.PARALLEL_TOOL_CALLS,
                    default=options.get(LocalAiConfigKey.PARALLEL_TOOL_CALLS, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.STRIP_EMOJIS,
                    default=options.get(LocalAiConfigKey.STRIP_EMOJIS, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.STRIP_EMPHASIS,
                    default=options.get(LocalAiConfigKey.STRIP_EMPHASIS, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.STRIP_LATEX,
                    default=options.get(LocalAiConfigKey.STRIP_LATEX, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.MANUAL_PROMPTING,
                    default=options.get(LocalAiConfigKey.MANUAL_PROMPTING, False),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.TEMPERATURE,
                    default=options.get(LocalAiConfigKey.TEMPERATURE, 1),
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=1, step=0.05, mode=NumberSelectorMode.SLIDER)
                ),
            }
        )

    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> SubentryFlowResult:
        """Handle user step to create a conversation subentry."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=await self.get_schema(),
            )
        user_input = user_input.copy()
        raw_name = user_input.get(CONF_NAME)
        custom_name = raw_name.strip() if isinstance(raw_name, str) else None
        if custom_name:
            user_input[CONF_NAME] = custom_name
        else:
            user_input.pop(CONF_NAME, None)

        raw_model = user_input.get(CONF_MODEL, "Local")
        model_name = self.strip_model_pathing(str(raw_model) if raw_model is not None else "Local")
        entry_title = custom_name or f"{model_name} AI Agent"

        return self.async_create_entry(title=entry_title, data=user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, object] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfigure step for a conversation subentry."""
        if user_input is not None:
            user_input = user_input.copy()
            raw_name = user_input.get(CONF_NAME)
            custom_name = raw_name.strip() if isinstance(raw_name, str) else None
            if custom_name:
                user_input[CONF_NAME] = custom_name
            else:
                user_input.pop(CONF_NAME, None)

            raw_model = user_input.get(CONF_MODEL, "Local")
            model_name = self.strip_model_pathing(
                str(raw_model) if raw_model is not None else "Local"
            )
            entry_title = custom_name or f"{model_name} AI Agent"

            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=entry_title,
                data=user_input,
            )

        options = self._get_reconfigure_subentry().data.copy()

        hass_apis = [api.get("value") for api in self.get_llm_apis()]
        options["llm_hass_api"] = [
            api for api in options.get("llm_hass_api", []) if api in hass_apis
        ]

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=await self.get_schema(options),
        )


class AITaskDataFlowHandler(LocalAiSubentryFlowHandler):
    """Handle subentry flow."""

    async def get_schema(self, options: dict[str, object] | None = None):
        """Return the configuration schema for AI task options."""
        if options is None:
            options = {}
        downloaded_models, has_live_models = await self.get_model_options(options)

        if raw_model := options.get(CONF_MODEL):
            default_model = str(raw_model)
        elif has_live_models:
            default_model = downloaded_models[0]["value"]
        else:
            default_model = "gemini-flash"

        default_title = self.strip_model_pathing(default_model)
        default_name: str = f"{default_title} AI Task"
        if raw_name := options.get(CONF_NAME):
            default_name = str(raw_name)

        return vol.Schema(
            {
                vol.Optional(
                    CONF_NAME,
                    default=default_name,
                ): str,
                vol.Required(
                    CONF_MODEL,
                    default=default_model,
                ): SelectSelector(
                    SelectSelectorConfig(options=downloaded_models, custom_value=True)
                ),
                vol.Optional(
                    LocalAiConfigKey.GENERATE_DATA,
                    default=options.get(LocalAiConfigKey.GENERATE_DATA, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.GENERATE_IMAGE,
                    default=options.get(LocalAiConfigKey.GENERATE_IMAGE, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.SUPPORT_ATTACHMENTS,
                    default=options.get(LocalAiConfigKey.SUPPORT_ATTACHMENTS, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.STRIP_EMOJIS,
                    default=options.get(LocalAiConfigKey.STRIP_EMOJIS, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.STRIP_EMPHASIS,
                    default=options.get(LocalAiConfigKey.STRIP_EMPHASIS, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.STRIP_LATEX,
                    default=options.get(LocalAiConfigKey.STRIP_LATEX, True),
                ): bool,
                vol.Optional(
                    LocalAiConfigKey.TEMPERATURE,
                    default=options.get(LocalAiConfigKey.TEMPERATURE, 1),
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=1, step=0.05, mode=NumberSelectorMode.SLIDER)
                ),
            }
        )

    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> SubentryFlowResult:
        """Handle user step to create an AI task subentry."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=await self.get_schema(),
            )
        user_input = user_input.copy()
        raw_name = user_input.get(CONF_NAME)
        custom_name = raw_name.strip() if isinstance(raw_name, str) else None
        if custom_name:
            user_input[CONF_NAME] = custom_name
        else:
            user_input.pop(CONF_NAME, None)

        raw_model = user_input.get(CONF_MODEL, "Local")
        model_name = self.strip_model_pathing(str(raw_model) if raw_model is not None else "Local")
        entry_title = custom_name or f"{model_name} AI Task"

        return self.async_create_entry(title=entry_title, data=user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, object] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfigure step for an AI task subentry."""
        if user_input is not None:
            user_input = user_input.copy()
            raw_name = user_input.get(CONF_NAME)
            custom_name = raw_name.strip() if isinstance(raw_name, str) else None
            if custom_name:
                user_input[CONF_NAME] = custom_name
            else:
                user_input.pop(CONF_NAME, None)

            raw_model = user_input.get(CONF_MODEL, "Local")
            model_name = self.strip_model_pathing(
                str(raw_model) if raw_model is not None else "Local"
            )
            entry_title = custom_name or f"{model_name} AI Task"

            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=entry_title,
                data=user_input,
            )

        options = self._get_reconfigure_subentry().data.copy()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=await self.get_schema(options),
        )
