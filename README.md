# Thread Studio

Ứng dụng web thử nghiệm chuyển ảnh logo ít màu thành đường thêu chạy theo hàng, xem trước và xuất DST/PES. Quy trình tham khảo phần mềm số hóa thêu; không dùng engine Wilcom, không tích hợp Wilcom và không đọc/ghi EMB.

## Chạy tại môi trường cloud

Python 3.12 và `uv`:

```sh
cd /workspace/wilcomsimu
UV_CACHE_DIR=/workspace/.cache/uv uv venv --allow-existing /workspace/.venvs/wilcomsimu
UV_CACHE_DIR=/workspace/.cache/uv uv pip sync --python /workspace/.venvs/wilcomsimu/bin/python requirements.txt
/workspace/.venvs/wilcomsimu/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

Giao diện ở `/`, kiểm tra dịch vụ qua `GET /health`. Không cần API key, cơ sở dữ liệu hoặc tài khoản Wilcom. Ảnh được xử lý trong bộ nhớ; ứng dụng không lưu ảnh tải lên.

## Sử dụng

### Tạo EXE trên Windows

1. Cài Python 3.12 bản 64-bit kèm Python Launcher trên Windows 10/11.
2. Giải nén toàn bộ mã nguồn vào một thư mục có quyền ghi.
3. Nhấp đúp `build-windows.bat`. Lần tạo đầu cần Internet để tải thư viện và PyInstaller 6.16.0.
4. Khi thành công, file thực thi ở `dist\ThreadStudio.exe`. Có thể chép file này sang máy Windows tương thích mà không cần cài Python.
5. Mở EXE: ứng dụng tự mở trình duyệt. Giữ cửa sổ console; nhấn Ctrl+C để thoát. Nếu trình duyệt không mở, nhập địa chỉ in trong cửa sổ console.

EXE chạy dịch vụ cục bộ trên 127.0.0.1 với cổng trống được chọn tự động; ảnh xử lý trên máy. Không cần cài Wilcom. Đây chưa phải bộ cài có chữ ký số. Quy trình đóng gói Windows được cung cấp để chạy trên Windows; chưa được xác minh bằng một lần build hoặc chạy trên Windows trong môi trường Linux này.

Có thể chạy launcher mà không đóng gói: `python desktop.py` (sau khi cài requirements).

Chọn PNG/JPEG/WebP dưới 10 MB, điều chỉnh chiều rộng (10–200 mm), số màu (2–12), khoảng cách hàng thêu (0.4–2 mm), rồi tạo mẫu. Chiều cao cũng giới hạn 200 mm. Xem mô phỏng và tải DST/PES. Ảnh logo, vùng màu phẳng là mục tiêu của bản đầu; ảnh chân dung chưa được tối ưu.

## Giới hạn

Đây là công cụ tạo mẫu thử, chưa thay thế quy trình số hóa chuyên nghiệp. Chưa có đường lót, satin, bù co kéo, chỉnh đối tượng hay tối ưu cắt chỉ. Nhiều vùng rời có thể tạo nhiều bước nhảy. Xem trước chỉ biểu diễn đường đi, không mô phỏng vải và độ phủ thực tế. DST không mang bảng màu chỉ; PES dùng bảng màu chỉ của định dạng. Luôn kiểm tra bằng phần mềm thêu và chạy mẫu thử trước khi sản xuất.

## API

`POST /api/digitize` nhận multipart: `image`, `width_mm`, `colors`, `spacing`, `ignore_white`. Trả kích thước, số mũi, các lớp màu/đường thêu theo mm và dữ liệu DST/PES mã hóa base64. Giới hạn 16 triệu điểm ảnh đầu vào, 100.000 mũi đầu ra. Bản thử nghiệm phục vụ phát triển nội bộ, chưa có xác thực hay hàng đợi xử lý cho triển khai công khai.
