# HACS V2 cho Gemini FastAPI Multi-Account V4

## Thay đổi

- `REQUEST_TIMEOUT`: 120 giây -> 145 giây.
- Mỗi request tới backend có ID riêng dạng `ha-<uuid>`.
- HACS gửi ID qua header `X-Request-ID`.
- Backend V4 dùng trực tiếp ID này trong log scheduler/failover/TTFB/structured-output.
- Home Assistant log start/completed/error cùng `request_id`.
- Áp dụng cho chat streaming, structured output, tool calls và image Responses API.
- `max_retries=0` giữ nguyên để backend là nơi duy nhất quyết định failover.

## Ví dụ đối chiếu log

Home Assistant:

```text
Gemini FastAPI request started request_id=ha-abc... model=... iteration=1 stream=true structured=False
```

Backend V4:

```text
account_id=gemini-phuoc event=account_selected request_id=ha-abc... scheduler=adaptive_ttfb
account_id=gemini-phuoc event=upstream_first_byte request_id=ha-abc... first_byte_ms=...
```
