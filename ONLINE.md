# Docker nội bộ và phân tích bằng ChatGPT

Các tệp này chuẩn bị ứng dụng để chạy trên VPS hoặc dịch vụ container. Chúng **không tự tạo máy chủ, tên miền hoặc website online**. Cần chọn nơi lưu trữ và có quyền triển khai ở đó.

## Quy trình phân tích

Mở **Phân tích thiết kế bằng ChatGPT**, chọn ảnh, ghi yêu cầu và nhấn phân tích. Máy chủ gửi ảnh đã bỏ metadata, thu nhỏ tối đa 1600 px cùng ghi chú tới OpenAI Responses API. PNG trong suốt được xem trên nền xám để giữ chữ trắng. Không tự gửi các mẫu huấn luyện cũ; ứng dụng không lưu ảnh hay ghi chú vào tệp. Yêu cầu đặt `store=false`; đây không phải cam kết không lưu dữ liệu theo mọi chính sách của nhà cung cấp.

AI đề xuất mô tả, vùng satin/tatami/cần chỉnh tay, lựa chọn nền, số màu và thông số. Bạn xem lại rồi nhấn **Áp dụng thông số gợi ý**. Bước này chỉ điền thông số chung, không tự phân đoạn chính xác các vùng hay chia cột satin. Nhấn **Tạo đường thêu** để chạy bộ tạo DST/PES hiện có; tiếp tục kiểm tra, sửa từng vùng và thêu thử. AI không dùng engine Wilcom.

Mặc định gọi `gpt-4.1-mini`; có thể đổi `THREAD_OPENAI_MODEL` sang mô hình hỗ trợ ảnh và Structured Outputs của Responses API. Khóa chỉ ở phía máy chủ. **Chi phí API tách biệt với thuê bao ChatGPT.** Giới hạn một phân tích đồng thời và 10 lượt/phút cho một tiến trình; không tự gọi lại khi lỗi. Nên đặt thêm hạn mức ở tài khoản API.

## Khởi động trên máy chủ

1. Cài Docker Engine và Docker Compose v2, lấy mã nguồn repository.
2. Sao chép `.env.example` thành `.env` và sửa bằng trình soạn thảo trên máy chủ:
   - `THREAD_APP_USERNAME`: tên đăng nhập, mặc định `admin`.
   - `THREAD_APP_PASSWORD`: mật khẩu riêng tối thiểu 12 ký tự, bắt buộc.
   - `THREAD_OPENAI_KEY`: khóa OpenAI API; nhập qua cấu hình bảo mật máy chủ/secret manager, không gửi trong chat hoặc commit.
   - `THREAD_OPENAI_MODEL`: mặc định `gpt-4.1-mini`.
3. Hạn chế quyền đọc `.env`, ví dụ `chmod 600 .env` trên Linux.
4. Kiểm tra cấu hình mà không in giá trị bí mật, rồi chạy:

```sh
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Mặc định cổng 8000 chỉ bind vào loopback máy chủ. Dùng đường hầm SSH hoặc reverse proxy HTTPS để vào từ máy khác. Đăng nhập HTTP Basic bằng tài khoản trong `.env`. Đây là tài khoản chung cho nhóm nội bộ; chưa có tài khoản riêng, phân quyền và lịch sử từng người. Không mở cổng HTTP trực tiếp ra Internet để truyền mật khẩu.

Không có khóa API vẫn tạo được DST/PES, nhưng nút phân tích bị vô hiệu hóa. Đổi `.env` cần tạo lại container: `docker compose up -d --force-recreate`. Ảnh xử lý trong bộ nhớ; upload tạm nằm ở tmpfs 64 MB, không có kho lưu thiết kế lâu dài. Container chạy bằng người dùng không phải root, filesystem chỉ đọc và không tăng quyền.

## HTTPS với tên miền thật

Đặt DNS trỏ tới VPS, mở cổng 80/443 và điền `THREAD_DOMAIN` trong `.env`:

```sh
docker compose -f compose.yaml -f compose.https.yaml config --quiet
docker compose -f compose.yaml -f compose.https.yaml up --build -d
```

Caddy xin chứng chỉ HTTPS và chuyển yêu cầu sang ứng dụng; giới hạn body 12 MB. Máy chủ cần truy cập được dịch vụ cấp chứng chỉ và `api.openai.com:443`. Healthcheck không cần đăng nhập; các trang và API khác được bảo vệ. Chỉ chạy cấu hình tên miền khi có DNS và quyền quản trị thực tế.

## Build trên mạng có CA nội bộ

Nếu mạng dùng CA nội bộ hợp lệ, truyền bundle CA công khai đã tin cậy dưới dạng BuildKit secret:

```sh
docker build --secret id=build_ca,src=/path/to/trusted-ca-bundle.pem -t thread-studio:online .
```

Không tắt xác minh TLS, không dùng `--trusted-host`. Bundle chỉ gắn vào bước cài dependencies, không được lưu trong image. VPS Internet thông thường không cần tùy chọn này. Nếu runtime cũng qua proxy TLS nội bộ, cấu hình CA tin cậy tại môi trường chạy. Không dùng API key/mật khẩu làm build argument hoặc sao chép vào image.

## Kiểm thử và xác minh

```sh
python -m unittest discover -s tests -v
```

Kiểm thử OpenAI dùng HTTP transport mô phỏng để kiểm tra payload ảnh/schema, phản hồi, lỗi, giới hạn và không lộ khóa. **Chưa chứng minh cuộc gọi thật thành công.** Cần khóa hợp lệ, hạn mức API và thử ảnh thật trước khi coi AI sẵn sàng. Container build và chạy được chưa chứng minh đã có website truy cập công khai; HTTPS cần kiểm tra riêng trên tên miền thật.

Trong Codex cloud, yêu cầu secret `THREAD_OPENAI_KEY` tới `api.openai.com` đã được lưu trong nháp. Điền qua Environment settings, không gửi trong chat. Ứng dụng cũng nhận `OPENAI_API_KEY` trên VPS, nhưng tên này được nền tảng dành riêng nên không dùng làm tên proxy secret trong nháp cloud.
