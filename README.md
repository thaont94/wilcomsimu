# Thread Studio

Ứng dụng web thử nghiệm chuyển ảnh logo ít màu thành satin cho nét hẹp, tatami cho mảng màu, xem trước và xuất DST/PES. Quy trình tham khảo phần mềm số hóa thêu; không dùng engine Wilcom, không tích hợp Wilcom và không đọc/ghi EMB.

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

### Satin cho nét, tatami cho mảng

- Mỗi thành phần liên thông cùng màu được xem là một vùng. Phân tích tim nét và bề rộng cục bộ ở độ phân giải 0.2 mm. Mặc định, bề rộng ở phân vị 95 không quá 4 mm được gợi ý satin; vùng rộng hơn dùng tatami. Có thể chỉnh ngưỡng 1–8 mm.
- Satin luân phiên điểm xuống kim ở hai mép theo hướng pháp tuyến của tim nét, giúp đường chỉ đổi hướng theo đường cong. Thông số khoảng hàng là khoảng tiến của một cặp mũi; hai điểm liên tiếp tiến khoảng nửa khoảng hàng. Nhánh và góc phức tạp có thể cần chia cột thủ công trong phần mềm thêu.
- Tatami chia mũi theo độ dài 1–4 mm, so le điểm xuống kim theo chu kỳ bốn hàng; góc thêu tùy chỉnh 0–180°. Lỗ trống được giữ lại, không nối mũi xuyên qua nền.
- Sau khi tạo, danh sách vùng cho phép đổi Tự động / Satin / Tatami. Đặt con trỏ vào lựa chọn để làm nổi bật vùng trong mô phỏng; đổi loại rồi nhấn Tạo đường thêu để tính lại và tải tệp mới. Satin bị từ chối cho vùng quá rộng trên 8 mm. Vùng quá nhỏ để dựng cột satin có thể được chuyển sang tatami kèm ghi chú.
- Thay ảnh, kích thước hoặc số màu sẽ xóa lựa chọn vùng cũ vì cách phân vùng có thể thay đổi. Thay thông số sẽ ẩn tệp tải cũ cho đến khi tính lại.

Đây là nhận diện hình học, không phải mô hình đã được huấn luyện từ DST và không phục hồi đối tượng EMB. Mẫu DST tham khảo chỉ dùng đối chiếu đường đi; không suy ra chắc chắn loại mũi từ định dạng này.

## Giới hạn

Đây là công cụ tạo mẫu thử, chưa thay thế quy trình số hóa chuyên nghiệp. Chưa có đường lót, bù co kéo, tách/chỉnh đường biên đối tượng, chia cột satin hay tối ưu cắt chỉ. Nét và mảng cùng màu chạm nhau vẫn là một vùng, có thể cần tách thủ công bên ngoài ứng dụng. Nhiều vùng rời có thể tạo nhiều bước nhảy. Mẫu rộng dưới độ phân giải 0.2 mm có thể mất chi tiết; vùng dưới ba pixel bị bỏ qua. Ảnh nhiều nhiễu bị từ chối khi vượt giới hạn số vùng. Xem trước chỉ biểu diễn đường đi, không mô phỏng vải và độ phủ thực tế. DST không mang bảng màu chỉ; PES dùng bảng màu chỉ của định dạng. Luôn kiểm tra bằng phần mềm thêu và chạy mẫu thử trước khi sản xuất.

## Kiểm thử

```sh
/workspace/.venvs/wilcomsimu/bin/python -m unittest discover -s tests -v
```

Kiểm tra hướng satin trên nét đứng và nét cong, lỗ trống của tatami, góc và độ dài mũi, nhịp xuống kim so le, sửa loại mũi từng vùng, giới hạn đầu vào và đọc lại DST/PES. Các bài này xác minh dữ liệu và hình học; chưa chứng minh chất lượng thêu trên vải hoặc độ tương đồng với mẫu Wilcom.

## API

`POST /api/digitize` nhận multipart: `image`, `width_mm`, `colors`, `spacing`, `ignore_white`, `stitch_length`, `angle`, `satin_width`, `object_types`. Trường `object_types` là chuỗi JSON ánh xạ ID vùng trả về từ lần tạo trước sang `auto`, `satin` hoặc `tatami`. Trả kích thước, số mũi, các lớp màu/đường thêu theo mm, danh sách `objects` có loại mũi, thống kê `object_counts` và dữ liệu DST/PES mã hóa base64. Giới hạn 16 triệu điểm ảnh đầu vào, 100.000 mũi đầu ra và 500 vùng; ảnh quá nhiều thành phần rời ở một màu cũng bị từ chối. Bản thử nghiệm phục vụ phát triển nội bộ, chưa có xác thực hay hàng đợi xử lý cho triển khai công khai.
