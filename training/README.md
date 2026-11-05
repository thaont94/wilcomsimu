# Mô hình phân vùng thử nghiệm — ba thiết kế

Đã thực sự fit Random Forest 48 cây, độ sâu tối đa 8, seed 42 trên ba cặp ảnh–DST: XÂY DỰNG (70 mm), GM247 (80 mm), MSTEK (70 mm). Mô hình dự đoán vùng satin/tatami từ hình học ảnh ở đơn vị mm. Đây không phải mô hình sinh chuỗi mũi kim hay bản sao engine Wilcom.

## Nhãn và đối chiếu

Ghi chú người dùng xác nhận GM247 và MSTEK dùng satin; XÂY DỰNG dùng satin cho chữ/viền và tatami cho mảng lớn. Vì DST không lưu nhãn đối tượng, vùng tatami XÂY DỰNG được đánh dấu bằng polygon thô sau khi xem ảnh và ghi chú. Bỏ qua dải 0.6 mm quanh đường chia chưa chắc chắn. Đây là nhãn yếu, cần người dùng duyệt thêm; không giả định đó là biên đối tượng chính xác của Wilcom.

DST được dùng để kiểm tra kích thước và độ khớp với ảnh. Sau căn theo bounding box, khoảng 99.6–100% điểm STITCH nằm cách vùng hình không quá 0.8 mm. Con số này chỉ kiểm tra cặp dữ liệu/căn chỉnh, không đo chất lượng đường thêu. Thông số spacing được lấy từ ghi chú và điều chỉnh bằng giao diện, không được học bởi mô hình này.

Đặc trưng gồm bán kính vùng, độ phủ lân cận và tính định hướng hình học ở nhiều tỷ lệ. Không dùng tên thiết kế, vị trí tuyệt đối, màu chỉ hoặc ảnh mẫu lưu sẵn để tra cứu. Mẫu gốc và DST của người dùng không nằm trong repository; chỉ có trọng số JSON, báo cáo và ví dụ annotation.

## Kết quả và giới hạn

Xem [report.json](report.json). Huấn luyện lấy 16.000 pixel mẫu, nhưng chỉ có **3 thiết kế độc lập**. Macro F1 khoảng 0.972 trên các pixel đã dùng học là kết quả khớp dữ liệu, **không phải độ chính xác trên logo mới**.

Đánh giá giữ lại cả thiết kế, không chia ngẫu nhiên pixel của một ảnh vào train và test:

| Thiết kế giữ lại | Kết quả classifier trước hậu xử lý |
| --- | --- |
| XÂY DỰNG | Hai mẫu học còn lại không có tatami, nên mô hình không nhận ra tatami; không thể đánh giá khả năng tổng quát tatami độc lập |
| GM247 | Chỉ khoảng 22% pixel satin được nhận đúng; mô hình chưa tổng quát tốt |
| MSTEK | Nhận đúng satin trên mẫu này; mẫu không có tatami nên chưa chứng minh phân biệt cả hai loại |

Vì vậy, mô hình **tắt mặc định**, chỉ dùng để thử nghiệm đối chiếu. Không có mục tiêu thêu trên vải đã được kiểm chứng. Vẫn có lỗi phân vùng, chưa học tim/hai mép satin, hướng kim, mũi lót, bù co kéo hoặc thứ tự thêu. Ngay trên GM247 đã học vẫn có thể xuất hiện mảnh tatami nhỏ; có thể sửa loại mũi từng vùng. Không báo cáo một con số “accuracy” chung để che các hạn chế này.

## Thử trong ứng dụng

Chọn **Mô hình 3 mẫu — thử nghiệm**, chọn **1 màu**, satin 0.36 mm; với XÂY DỰNG, tatami 0.4 mm và chiều dài mũi 4 mm theo ghi chú. Giữ nguyên hai tham số tatami không ảnh hưởng các vùng satin. Chọn nền phù hợp: XÂY DỰNG nền trắng, GM247 tự động nhận nền đỏ, MSTEK nền đen hoặc chỉ bỏ vùng trong suốt tùy tệp.

Cắt sát vùng logo trước khi nhập để chiều rộng mm ứng với logo chứ không gồm lề ảnh. Đánh giá nội bộ ba mẫu đã dùng foreground mask được kiểm tra riêng và crop sát hình; chưa chứng minh bộ tự bỏ nền phù hợp cho mọi ảnh. Kết quả đã xuất và đọc lại được cả DST/PES cho ba mẫu; khả năng đọc tệp không đồng nghĩa chất lượng giống tệp chuẩn.

## Huấn luyện lại

```sh
cd /workspace/wilcomsimu
UV_CACHE_DIR=/workspace/.cache/uv uv pip install --python /workspace/.venvs/wilcomsimu/bin/python -r requirements.txt -r training/requirements.txt
# Đặt manifest cạnh thư mục dữ liệu theo đường dẫn tương đối trong ví dụ.
/workspace/.venvs/wilcomsimu/bin/python -m training.train_regions --manifest /workspace/training-data/three-designs/manifest.json
```

[manifest.example.json](manifest.example.json) lưu cách chọn foreground và polygon của lần thử này. Có thể dùng đường dẫn tuyệt đối hoặc đường dẫn tính từ thư mục chứa manifest. Định nghĩa `blue`, `white`, `cyan` là các bộ chọn đã kiểm tra riêng cho ba mẫu, không phải thuật toán tự ghép mọi logo. Cần xem và ghi nhãn cho thiết kế mới; không tự gán tất cả ảnh mới là satin khi chưa biết.

Mặc định lưu trọng số vào `models/region-guide.json`, báo cáo vào `training/report.json`; chỉ chạy lệnh khi có ý định thay thế hai tệp này. Huấn luyện lặp cùng đầu vào và phiên bản đã cho cùng SHA-256 trọng số trong lần xác minh này. Seed, phiên bản sklearn và hash nguồn được ghi trong báo cáo.

Runtime đọc JSON bằng NumPy/SciPy, không nạp pickle và không cần sklearn. Bộ tạo EXE có đóng gói trọng số; kiểm thử chương trình đóng gói Linux không thay thế việc kiểm chứng EXE Windows.

Để cải thiện tiếp cần thêm **nhiều thiết kế độc lập có cả satin và tatami**, nhất là nét cong, chữ đậm, điểm nối và mảng lớn; giữ một tập ngoài huấn luyện để đánh giá. Các mẫu sửa nhãn phải được phiên bản hóa cùng manifest.
