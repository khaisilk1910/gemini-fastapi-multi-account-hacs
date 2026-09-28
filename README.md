# Gemini FastAPI Multi-Account HACS

Tích hợp HACS cho Home Assistant, tối ưu riêng để kết nối với container **gemini-fastapi-multi-account** qua API OpenAI-compatible (`/v1`).

Repo HACS: `gemini-fastapi-multi-account-hacs`  
Home Assistant domain: `gemini_fastapi_multi_account`


## Cài đặt qua HACS

Nhấn nút dưới đây để mở trực tiếp repository này trong HACS:

[![Mở repository trong HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=khaisilk1910&repository=gemini-fastapi-multi-account-hacs&category=integration)

Sau đó:

1. Chọn **Download** trong HACS để cài đặt tích hợp.
2. Khởi động lại Home Assistant.
3. Vào **Settings → Devices & services → Add integration**.
4. Tìm **gemini-fastapi-multi-account-hacs** và hoàn tất cấu hình theo giao diện.

## Mục tiêu của bản này

- Không gọi API mạng trong `async_setup_entry`, vì vậy container Gemini đang tắt/chậm không giữ quá trình khởi động Home Assistant chờ timeout.
- Dùng HTTP client dùng chung của Home Assistant; mọi request đều bất đồng bộ.
- Tự chuẩn hóa URL về `/v1`. Có thể nhập `http://HOST:8000`, `http://HOST:8000/v1` hoặc thậm chí URL endpoint `/v1/chat/completions`.
- Timeout kiểm tra model khi cấu hình: 5 giây. Timeout request runtime: 120 giây.
- `max_retries=0` ở OpenAI SDK để tránh retry trùng request; failover/retry tài khoản do chính container multi-account xử lý.
- Hỗ trợ streaming Assist, Home Assistant tools/function calling, `parallel_tool_calls`, structured output, attachments và AI Task image generation qua `/v1/responses`.
- Giảm overhead streaming: bỏ `demoji`, bỏ `webcolors`, không đẩy các thao tác chuỗi nhẹ vào executor ở mỗi chunk.
- Pin `openai==3.10.0`, đồng bộ với Home Assistant hiện hành, và `pylatexenc==2.11`.
- Có bản dịch English/Vietnamese, Hassfest + HACS validation và workflow tạo GitHub Release theo tag.

## Yêu cầu

- Home Assistant 2025.7.0 trở lên; khuyến nghị Home Assistant bản ổn định mới nhất.
- HACS 2.0.5 trở lên.
- Container `gemini-fastapi-multi-account` đang hoạt động và truy cập được từ Home Assistant.

> Nếu bạn đang cài `Local OpenAI LLM` cũ, nên gỡ/disable bản cũ trước khi cài bản này để tránh hai integration cùng tải các phiên bản dependency OpenAI khác nhau.

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

## Cài bằng HACS Custom Repository

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

## Tạo repo GitHub từ repo rỗng đã có

Repo đích:

```text
https://github.com/khaisilk1910/gemini-fastapi-multi-account-hacs
```

Trên Git CMD/Terminal:

```bash
git clone https://github.com/khaisilk1910/gemini-fastapi-multi-account-hacs.git
cd gemini-fastapi-multi-account-hacs
```

Giải nén gói source được cung cấp rồi **chép nội dung bên trong thư mục** `gemini-fastapi-multi-account-hacs` vào thư mục repo vừa clone. Không tạo thêm một tầng thư mục lồng nhau.

Sau đó:

```bash
git add .
git commit -m "Initial Gemini FastAPI Multi-Account HACS integration"
git branch -M main
git push -u origin main
```

Tạo release đầu tiên:

```bash
git tag -a v1.0.0 -m "v1.0.0"
git push origin v1.0.0
```

Tag `v*` sẽ chạy workflow `Release`, tạo asset `gemini_fastapi_multi_account.zip`. Mỗi lần phát hành bản mới, tăng `version` trong `manifest.json`, commit/push, rồi tạo tag tương ứng, ví dụ `v1.0.1`.

## Kiểm tra nhanh API trước khi thêm integration

Từ một máy có thể truy cập container:

```bash
curl http://HOST:8000/health
curl -H "Authorization: Bearer YOUR_API_KEY" http://HOST:8000/v1/models
```

Nếu container không bật API key thì bỏ header `Authorization`.

## Thiết kế liên quan hiệu năng Home Assistant

`async_setup_entry` chỉ tạo client và cache metadata nền tảng của OpenAI SDK bằng executor; không thực hiện HTTP request. Vì vậy một container Gemini lỗi/offline sẽ không làm Home Assistant chờ 5–120 giây trong startup. Request LLM chạy bất đồng bộ và dùng shared HTTPX client của Home Assistant.

SDK retry được tắt có chủ đích. Container của dự án đã có scheduler multi-account, cooldown và failover; retry thêm ở tầng HACS có thể làm request bị nhân đôi và tăng độ trễ, đặc biệt với tool/action.

## Bản quyền

Integration này là bản sửa đổi/phái sinh của `hass_local_openai_llm` và giữ giấy phép **Apache License 2.0**. Xem `LICENSE` và `NOTICE`.

Container `gemini-fastapi-multi-account` là dự án riêng và giữ giấy phép riêng của container; mã server không được nhúng vào repo HACS này.
