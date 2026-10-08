# Gemini FastAPI Multi-Account HACS

<p align="center">
  <img src="custom_components/gemini_fastapi_multi_account/brand/icon.png" alt="Gemini FastAPI Multi-Account" width="250" height="250">
</p>


## Yêu cầu

- Home Assistant 2026.10.0 trở lên; tối ưu theo API của Home Assistant 2026.10.
- HACS 2.0.5 trở lên.
- Container `gemini-fastapi-multi-account` đang hoạt động và truy cập được từ Home Assistant.

> Từ v1.3.0 integration không còn phụ thuộc OpenAI Python SDK; giao tiếp với Gemini FastAPI bằng HTTP trực tiếp qua HTTPX session dùng chung của Home Assistant.

## URL nên dùng

Nếu Home Assistant OS/Supervised chạy ở máy khác hoặc không cùng Docker network:

```text
http://192.168.1.50:8000
```

Nếu Home Assistant Container và Gemini FastAPI ở **cùng một Docker network**:

```text
http://gemini-fastapi-multi-account:8000
```

Không dùng `127.0.0.1:8000` từ Home Assistant Container trừ khi API thực sự chạy trong chính container Home Assistant.

API key trong integration phải khớp với `CONFIG_SERVER__API_KEY` của container. Nếu server để `api_key: null`/không bật xác thực, có thể để trống ô API key.


## Cài đặt qua HACS

Nhấn nút dưới đây để mở trực tiếp repository này trong HACS:

[![Mở repository trong HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=khaisilk1910&repository=gemini-fastapi-multi-account-hacs&category=integration)

Sau đó:

1. Chọn **Download** trong HACS để cài đặt tích hợp.
2. Khởi động lại Home Assistant.
3. Vào **Settings → Devices & services → Add integration**.
4. Tìm **Gemini FastAPI Multi-Account** và hoàn tất cấu hình theo giao diện.


### Cài bằng HACS Custom Repository

1. Push repo này lên GitHub.
2. Vào **HACS → Integrations → dấu ba chấm → Custom repositories**.
3. Thêm:

```text
https://github.com/khaisilk1910/gemini-fastapi-multi-account-hacs
```

4. Category: **Integration**.
5. Tìm **Gemini FastAPI Multi-Account** → Download.
6. Restart Home Assistant.
7. Vào **Settings → Devices & services → Add integration**.
8. Tìm **Gemini FastAPI Multi-Account**.
9. Nhập Server URL và API key.
10. Thêm Conversation Agent và/hoặc AI Task subentry, chọn model từ `/v1/models`.

Việc kiểm tra `/v1/models` chỉ diễn ra khi cấu hình/mở form chọn model, không chạy trong quá trình boot Home Assistant.

### Tương thích Home Assistant 2026.10+

Từ version **1.3.0**, integration **không còn phụ thuộc `openai` Python package**. Backend Gemini FastAPI đã cung cấp API OpenAI-compatible nên integration gọi trực tiếp `/v1/models`, `/v1/chat/completions` và `/v1/responses` bằng HTTPX client dùng chung của Home Assistant. Điều này loại bỏ xung đột package constraint khi Home Assistant nâng OpenAI SDK.

Bản 1.3.0 đặt Home Assistant tối thiểu là **2026.10.0** và dùng API hiện hành của Home Assistant gồm `ConfigEntry.runtime_data`, `ConversationEntity` + `ChatLog`, config subentries và `AITaskEntity`.


## Tải lại integration

Từ version 1.2.0, integration cung cấp hai cách tải lại an toàn:

- Khi config entry đang **Loaded**, mở integration → **Entities** và bấm entity nút **Tải lại tích hợp / Reload integration**.
- Nếu config entry đang **Not loaded** nên button entity chưa tồn tại, vào **Developer Tools → Actions** và chạy action `gemini_fastapi_multi_account.reload`. Action này được đăng ký ở cấp integration nên có thể yêu cầu Home Assistant nạp lại cả config entry đang `Not loaded`.

Home Assistant không cho custom integration chèn nút tùy ý trực tiếp vào card ở trang **Settings → Devices & services → Integrations**, vì vậy nút được triển khai đúng chuẩn dưới dạng `button` entity, kèm action quản trị để xử lý cả trạng thái `Not loaded`.

Cả hai cách đều dùng `async_schedule_reload()` của Home Assistant để tránh race với setup retry.


## Kiểm tra nhanh API trước khi thêm integration

Từ một máy có thể truy cập container:

```bash
curl http://HOST:8000/health
curl -H "Authorization: Bearer YOUR_API_KEY" http://HOST:8000/v1/models
```

Nếu container không bật API key thì bỏ header `Authorization`.


## Bản quyền

Integration này là bản sửa đổi/phái sinh của `hass_local_openai_llm` và giữ giấy phép **Apache License 2.0**. Xem `LICENSE` và `NOTICE`.

Container `gemini-fastapi-multi-account` là dự án riêng và giữ giấy phép riêng của container; mã server không được nhúng vào repo HACS này.


## V4 request correlation

Version 1.1.0 is tuned for Gemini FastAPI Multi-Account V4:

- Client request timeout is 145 seconds.
- Every chat/tool iteration and image request gets a unique ID such as `ha-...`.
- The integration sends that value in the `X-Request-ID` header.
- Gemini FastAPI V4 accepts this header and writes the same request ID into account selection, timeout, failover, first-byte, structured-output and success/failure logs.
- Home Assistant logs request start, completion and errors with the same `request_id`.
- SDK retries remain disabled so a Home Assistant retry cannot race with backend account failover.


### SSE compatibility (v1.3.1)

The native HTTPX client raises errors if the backend returns a stream-level error
frame or closes its SSE stream before `[DONE]`. HTTP health/model requests and
initialization remain independent: Home Assistant starts without contacting the
Gemini gateway.
