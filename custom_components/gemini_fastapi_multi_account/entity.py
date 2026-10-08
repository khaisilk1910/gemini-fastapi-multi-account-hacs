"""Base entity for Gemini FastAPI Multi-Account."""

from __future__ import annotations

from uuid import uuid4

import probatio as vol

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL, CONF_PROMPT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from . import LocalAiConfigEntry
from .api import ApiClientError, ImageGenerationResult, extract_response_output_text
from .const import DOMAIN, LOGGER, MAX_TOOL_ITERATIONS, LocalAiConfigKey
from .helpers import (
    _convert_completion_messages_to_response_input,
    _convert_content_to_chat_message,
    _format_structured_output,
    _format_tool,
    _latex_to_text,
    _strip_emojis,
    _strip_emphasis_markers,
    _transform_stream,
    ChatCompletionMessage,
)
from .prompt import format_custom_prompt


class LocalAiEntity(Entity):
    """Base entity for Gemini FastAPI Multi-Account."""

    _attr_has_entity_name = True

    def __init__(self, entry: LocalAiConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Gemini FastAPI Multi-Account",
            model=subentry.data.get(CONF_MODEL, "Local"),
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    def model(self) -> str:
        """Return the model name."""
        return str(self.subentry.data.get(CONF_MODEL, "Local"))

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
        user_input: conversation.ConversationInput | None = None,
        force_image: bool = False,
    ) -> None:
        """Generate an answer for the chat log."""
        options = self.subentry.data
        strip_emojis = bool(options.get(LocalAiConfigKey.STRIP_EMOJIS))
        strip_emphasis = bool(options.get(LocalAiConfigKey.STRIP_EMPHASIS))
        strip_latex = bool(options.get(LocalAiConfigKey.STRIP_LATEX))
        if structure is not None:
            strip_emphasis = False
            strip_latex = False
        raw_temp = options.get(LocalAiConfigKey.TEMPERATURE, 1)
        temperature = float(raw_temp) if isinstance(raw_temp, int | float) else 1.0
        parallel_tool_calls = bool(options.get(LocalAiConfigKey.PARALLEL_TOOL_CALLS, True))

        tools: list[dict[str, object]] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in sorted(chat_log.llm_api.tools, key=lambda tool: tool.name)
            ]

        messages: list[ChatCompletionMessage] = [
            m
            for content in chat_log.content
            if (m := await _convert_content_to_chat_message(content, self.model)) is not None
        ]

        if options.get(LocalAiConfigKey.MANUAL_PROMPTING, False) and user_input:
            prompt = format_custom_prompt(
                self.hass, str(options.get(CONF_PROMPT, "")), user_input, tools
            ).strip()
            new_system_message: ChatCompletionMessage = {"role": "system", "content": prompt}
            found = False
            for i, msg in enumerate(messages):
                if msg["role"] == "system":
                    messages[i] = new_system_message
                    found = True
                    break

            if not found:
                messages.insert(0, new_system_message)

        if force_image:
            await self._async_handle_image_response(
                chat_log,
                messages,
                strip_emojis,
                strip_emphasis,
                strip_latex,
                temperature,
            )
            return

        client = self.entry.runtime_data

        for _iteration in range(MAX_TOOL_ITERATIONS):
            request_id = f"ha-{uuid4().hex}"
            request_headers = {"X-Request-ID": request_id}
            LOGGER.info(
                "Gemini FastAPI request started request_id=%s model=%s iteration=%d "
                "stream=true structured=%s",
                request_id,
                self.model,
                _iteration + 1,
                structure is not None,
            )
            payload: dict[str, object] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "parallel_tool_calls": parallel_tool_calls,
                "prompt_cache_key": chat_log.conversation_id,
                "stream": True,
            }
            if tools:
                payload["tools"] = tools
            if structure:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": _format_structured_output(
                        structure_name or "response", structure, chat_log.llm_api
                    ),
                }
            try:
                result_stream = client.chat_completions_stream(
                    payload, extra_headers=request_headers
                )
            except ApiClientError as err:
                LOGGER.error(
                    "Error requesting response from API request_id=%s: %s", request_id, err
                )
                raise HomeAssistantError(
                    f"Error talking to API (request_id={request_id}): {err}"
                ) from err

            try:
                messages.extend(
                    [
                        msg
                        async for content in chat_log.async_add_delta_content_stream(
                            self.entity_id,
                            _transform_stream(
                                result_stream, strip_emojis, strip_emphasis, strip_latex
                            ),
                        )
                        if (msg := await _convert_content_to_chat_message(content, self.model))
                        is not None
                    ]
                )
            except ApiClientError as err:
                LOGGER.error(
                    "Gemini FastAPI stream failed request_id=%s status_code=%s: %s",
                    request_id,
                    err.status_code,
                    err,
                )
                raise HomeAssistantError(
                    f"Error talking to API (request_id={request_id}): {err}"
                ) from err
            except Exception as err:
                LOGGER.exception(
                    "Error handling API response request_id=%s: %s", request_id, err
                )
                raise HomeAssistantError(
                    f"Error handling streamed API response (request_id={request_id})"
                ) from err

            LOGGER.info(
                "Gemini FastAPI request completed request_id=%s model=%s iteration=%d",
                request_id,
                self.model,
                _iteration + 1,
            )

            if not chat_log.unresponded_tool_results:
                break

    async def _async_handle_image_response(
        self,
        chat_log: conversation.ChatLog,
        messages: list[ChatCompletionMessage],
        strip_emojis: bool,
        strip_emphasis: bool,
        strip_latex: bool,
        temperature: float,
    ) -> None:
        """Generate an image response using the Responses API."""
        response_input = _convert_completion_messages_to_response_input(messages)

        client = self.entry.runtime_data

        request_id = f"ha-{uuid4().hex}"
        request_headers = {"X-Request-ID": request_id}
        LOGGER.info(
            "Gemini FastAPI image request started request_id=%s model=%s",
            request_id,
            self.model,
        )
        try:
            response = await client.create_response(
                {
                    "model": self.model,
                    "input": response_input,
                    "prompt_cache_key": chat_log.conversation_id,
                    "temperature": temperature,
                    "stream": False,
                    "store": True,
                    "tool_choice": {"type": "image_generation"},
                    "tools": [
                        {
                            "type": "image_generation",
                            "model": self.model,
                            "output_format": "png",
                        }
                    ],
                },
                extra_headers=request_headers,
            )
        except ApiClientError as err:
            LOGGER.error(
                "Error requesting image response from API request_id=%s: %s", request_id, err
            )
            raise HomeAssistantError(
                f"Error talking to API (request_id={request_id}): {err}"
            ) from err

        LOGGER.info(
            "Gemini FastAPI image request completed request_id=%s model=%s",
            request_id,
            self.model,
        )
        LOGGER.debug("Received image response from API: %s", response)
        text_output = extract_response_output_text(response)

        LOGGER.debug("Extracted text_output before filtering: %s", text_output)
        if strip_emojis and text_output:
            text_output = await _strip_emojis(text_output)
        if strip_latex and text_output:
            text_output = await _latex_to_text(text_output)
        if strip_emphasis and text_output:
            text_output = await _strip_emphasis_markers(text_output)

        if text_output:
            text_output = text_output.strip() or None

        LOGGER.debug("Final text_output after filtering: %s", text_output)

        image_call: ImageGenerationResult | None = None
        output_items = response.get("output")
        if isinstance(output_items, list):
            for item in output_items:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "image_generation_call" and "result" not in item:
                    continue
                result = item.get("result")
                if result is not None and not isinstance(result, str):
                    result = str(result)
                candidate = ImageGenerationResult(
                    result=result,
                    output_format=(
                        str(item.get("output_format")) if item.get("output_format") else None
                    ),
                    size=str(item.get("size")) if item.get("size") else None,
                    revised_prompt=(
                        str(item.get("revised_prompt")) if item.get("revised_prompt") else None
                    ),
                )
                if image_call is None or image_call.result is None:
                    image_call = candidate

        if image_call is None and text_output is None:
            raise HomeAssistantError(
                f"No image response returned from API (request_id={request_id})"
            )

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=self.entity_id,
                content=text_output,
                native=image_call,
            )
        )
