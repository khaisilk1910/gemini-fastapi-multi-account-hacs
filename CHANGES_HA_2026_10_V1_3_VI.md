# Gemini FastAPI Multi-Account HACS v1.3.0 — Home Assistant 2026.10 native HTTP

## Mục tiêu

Loại bỏ hoàn toàn dependency OpenAI Python SDK khỏi custom integration để tránh xung đột package constraint khi Home Assistant thay đổi phiên bản `openai` trong Core.

## Thay đổi chính

- Không còn `openai` trong `manifest.json` hoặc `pyproject.toml`.
- Gọi trực tiếp backend OpenAI-compatible qua `/v1/models`, `/v1/chat/completions` và `/v1/responses`.
- Dùng `homeassistant.helpers.httpx_client.get_async_client()` để tái sử dụng HTTPX client/session do Home Assistant quản lý.
- Giữ nguyên `X-Request-ID` để đối chiếu log Home Assistant ↔ backend multi-account.
- Tự giải mã SSE streaming và `[DONE]`; không có retry ở HACS, backend vẫn là nơi quyết định failover/retry.
- Dùng typed `ConfigEntry.runtime_data` để lưu native client.
- Cập nhật trực tiếp sang `probatio` theo Home Assistant 2026.10.
- Dùng `ToolResultContent.result.data` thay cho compatibility property `tool_result` đã deprecated.
- Giữ `ConversationEntity` + `ChatLog`, AI Task, attachment, structured output, image generation và Home Assistant LLM tool calling.
- Không thực hiện network I/O trong `async_setup_entry`, vì vậy backend tạm restart không làm config entry fail load.
- Home Assistant tối thiểu của nhánh này: 2026.10.0.

## Dependency còn lại

Chỉ còn `pylatexenc>=2.11,<3` cho tùy chọn chuyển LaTeX sang text. Integration không còn phụ thuộc OpenAI SDK.
