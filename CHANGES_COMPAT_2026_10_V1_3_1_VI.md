# HACS v1.3.1: Tương thích SSE / Backend

- Nhận diện `{ "error": ... }` trong stream Chat Completions, kể cả sau HTTP 200, và trả lỗi rõ ràng tới Home Assistant.
- Phát hiện stream bị ngắt trước `data: [DONE]`, không ghi nhận câu trả lời thiếu là thành công.
- Kiểm tra định dạng từng JSON SSE event; dùng `Accept: text/event-stream`.
- Không kiểm tra mạng trong `async_setup_entry`: đảm bảo Home Assistant không bị chặn khởi động khi backend mất kết nối.
- Giữ lại client HTTPX chia sẻ do Home Assistant quản lý và các cấu hình hiện có.
