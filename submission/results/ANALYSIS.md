# Phân tích kết quả huấn luyện so sánh: `raw` vs `clean`

## 1. Bảng tổng hợp kết quả thực nghiệm (YOLO26n, 20 epochs, imgsz=640, batch=16)

| Biến thể | Ảnh train khai báo | Ảnh thực train (sau lọc nội bộ) | Seed | mAP50 | mAP50-95 | Precision | Recall | AP50 `car` | AP50 `person` | AP50 `truck` | AP50 `bus` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `raw` | 224 | 213 | 0 | 0.7256 | 0.5144 | 0.8068 | 0.6291 | 0.7511 | 0.8126 | 0.6574 | 0.6811 |
| `raw` | 224 | 213 | 1 | 0.7259 | 0.5090 | 0.7203 | 0.6689 | 0.7239 | 0.8315 | 0.6395 | 0.7087 |
| **TB `raw`** | **224** | **213** | **0, 1** | **0.726 ± 0.000** | **0.512 ± 0.004** | **0.764 ± 0.061** | **0.649 ± 0.028** | **0.7375** | **0.8221** | **0.6485** | **0.6949** |
| `clean` | 203 | 203 | 0 | 0.6813 | 0.4766 | 0.8310 | 0.5618 | 0.7097 | 0.8341 | 0.4841 | 0.6972 |
| `clean` | 203 | 203 | 1 | 0.7163 | 0.4953 | 0.7606 | 0.6306 | 0.7716 | 0.8136 | 0.5876 | 0.6924 |
| **TB `clean`** | **203** | **203** | **0, 1** | **0.699 ± 0.025** | **0.486 ± 0.013** | **0.796 ± 0.050** | **0.596 ± 0.049** | **0.7407** | **0.8239** | **0.5359** | **0.6948** |

---

## 2. Trả lời 5 câu hỏi phân tích cốt lõi

### Câu 1: Chênh lệch `mAP50(clean) - mAP50(raw)` so với độ lệch chuẩn giữa các seed & giới hạn kết luận với 2 seed
* **Độ chênh lệch trung bình:** $\Delta \text{mAP50} = 0.6988 - 0.7258 = -0.0270$ (`-2.70%`), trong khi độ lệch chuẩn giữa 2 seed của `clean` là $\pm 0.0247$ ($\approx 0.025$, dao động từ `0.6813` ở seed 0 lên `0.7163` ở seed 1).
* **Ý nghĩa thống kê:** Biên độ chênh lệch tuyệt đối (`0.027`) gần như tương đương đúng $1\sigma$ độ nhiễu khởi tạo ngẫu nhiên giữa 2 seed của `clean` (`0.025`), và nếu xét riêng `seed 1` thì `clean` (`0.7163`) tiệm cận sát `raw` (`0.7259`).
* **Giới hạn kết luận với 2 seed:** Với cỡ mẫu $n=2$ seed trên tập train nhỏ (~200 ảnh), phương sai do thứ tự batch/augmentation (Mosaic, RandAugment) còn lớn nên **chưa đủ ý nghĩa thống kê để khẳng định `clean` kém hơn `raw` về năng lực tổng quát hóa thực sự**. Cần chạy tối thiểu 3–5 seed và loại bỏ rò rỉ dữ liệu test khỏi `raw` trước khi đưa ra kết luận cuối cùng.

### Câu 2: `raw` thực sự train trên bao nhiêu ảnh? (Phân tích log cảnh báo Ultralytics)
* Mặc dù khai báo **224 ảnh** (và chỉ có 218 file nhãn), log quét dữ liệu của Ultralytics ở Bước 6 cho thấy:
  `train: Scanning ... 216 images, 19 backgrounds, 11 corrupt` $\rightarrow$ **`Using 213 train, 40 val images`**.
* Như vậy, **`raw` thực tế chỉ huấn luyện trên 213 ảnh** (194 ảnh có nhãn hợp lệ + 19 ảnh background không nhãn), vì bộ nạp dữ liệu của Ultralytics đã tự động loại bỏ **11 ảnh/nhãn lỗi cú pháp nghiêm trọng**:
  * **2 ảnh hỏng file vật lý:** `img_0010.jpg` (cannot identify image file) và `img_0136.jpg` (truncated 26 bytes).
  * **4 nhãn sai ID lớp ngoài `[0..3]`:** `img_0020.jpg` (class `93`), `img_0104.jpg` (class `7`), `img_0194.jpg` (class `4`), `img_0199.jpg` (class `4`).
  * **4 nhãn sai tọa độ / giá trị âm:** `img_0014.jpg`, `img_0022.jpg` (out of bounds), `img_0099.jpg`, `img_0117.jpg` (negative values `-1`).
  * **1 nhãn sai cấu trúc cột:** `img_0179.jpg` (inhomogeneous shape).
* Trong khi đó, `clean` đạt **203/203 ảnh hợp lệ (`0 corrupt`)** và số ảnh background rỗng giảm mạnh từ **19** xuống chỉ còn **4** nhờ bước `autofix` khôi phục nhãn thiếu bằng Second Opinion.

### Câu 3: `raw` có ảnh trùng với tập `test` không và điểm số bị thổi phồng như thế nào?
* **Có rò rỉ dữ liệu nghiêm trọng (`LEAK_TEST`):** Pipeline AutoQC đã phát hiện và loại bỏ khỏi `clean` các ảnh trong `data/raw` trùng lặp nội dung (gần như giống hệt về pHash/dHash, `phash_dist <= 8`) với tập đánh giá `data/test` và `data/gold_val`.
* **Tác động thổi phồng điểm số của `raw`:** Vì các ảnh `LEAK_TEST` được giữ nguyên trong tập train của `raw`, mô hình `raw` được học trực tiếp trên chính các mẫu (hoặc khung hình gần kề) xuất hiện trong tập `test`, tạo ra hiện tượng **học vẹt do rò rỉ dữ liệu (data leakage inflation)** làm điểm mAP50 của `raw` bị đẩy cao giả tạo lên `0.726` (đặc biệt ở lớp `truck` đạt `0.6485` so với `0.5359` của `clean` — một phần vì `clean` mất đi các mẫu `truck` trùng với tập test và số lượng mẫu `truck` vốn ít nhất tập dữ liệu, chỉ 32–41 box).
* **Cách kiểm chứng định lượng:** Lọc tách tập `data/test` thành 2 nhóm (`test_leaked` gồm các ảnh có cặp trùng với `data/raw` theo báo cáo `02_error_list_v1.csv`, và `test_unseen` gồm các ảnh hoàn toàn không trùng), sau đó đánh giá lại trọng số `raw_seed0/best.pt` và `clean_seed0/best.pt` trên `test_unseen`. Độ chênh điểm của `raw` giữa `test_leaked` và `test_unseen` chính là phần điểm bị thổi phồng do rò rỉ.

### Câu 4: Lớp nào (`car` / `person` / `truck` / `bus`) được lợi nhất và giải thích từ `02_error_list_v1`
* **Lớp được lợi rõ rệt nhất là `person` và `car`** (đồng thời Precision tổng thể tăng từ `0.764` lên `0.796`, +3.2%):
  * **`person`:** Tăng từ trung bình `0.8221` (`raw`) lên **`0.8239` (`clean`)** (riêng `seed 0` đạt **`0.8341`** so với `0.8126` của `raw`, tăng **+2.15%**).
  * **`car`:** Tăng trung bình từ `0.7375` (`raw`) lên **`0.7407` (`clean`)** (riêng `seed 1` nhảy vọt lên **`0.7716`** so với `0.7239` của `raw`, tăng **+4.77%**).
* **Giải thích từ phân bố lỗi trong `02_error_list_v1`:**
  1. Trong `data/raw`, phần lớn lỗi gán sai ID lớp (`class 4, 7, 93, -1`), lệch/tràn biên (`OOB`), box vi mô (`TINY_BOX`) và bỏ sót nhãn (`MISSING_LABEL` ở 19 ảnh background) rơi tập trung vào 2 lớp chiếm mật độ cao nhất là `car` (tăng từ 537 lên **575 box** sau khi `autofix` bổ sung nhãn thiếu) và `person` (loại bỏ được 21 box nhiễu từ 122 xuống **101 box** chuẩn xác).
  2. Nhờ loại bỏ các box nhiễu/sai nhãn và bổ sung các box bị sót qua `second_opinion` (`conf >= 0.6`), mô hình `clean` học được ranh giới đặc trưng sạch hơn hẳn, thể hiện trực tiếp qua **Precision tăng từ `0.764` lên `0.796`** (giảm mạnh dự đoán dương tính giả).
  3. Ngược lại, lớp `truck` bị giảm AP50 (`0.6485` $\rightarrow$ `0.5359`) do đây là lớp thiểu số (chỉ ~32–41 box trên toàn tập); khi loại bỏ các ảnh trùng/rò rỉ và giữ lại 38 ảnh cảnh báo chưa duyệt, số lượng mẫu `truck` đa dạng bị thu hẹp khiến mô hình dễ nhầm lẫn giữa `truck` và `bus`/`car` lớn.

### Câu 5: `clean` còn lỗi gì? Hàng đợi duyệt có vượt ngân sách không? Đây đã là chặn trên của "dữ liệu sạch" chưa?
* **Các lỗi còn tồn đọng trong `clean`:**
  * Không còn bất kỳ lỗi nghiêm trọng (`error`) nào về định dạng, kích thước, trùng lặp hay rò rỉ dữ liệu.
  * Tuy nhiên, trong 203 ảnh xuất ra `clean_v1`, vẫn còn **38 ảnh mang cờ cảnh báo (`warning`, chiếm `18.72%`)** — chủ yếu là các ca cảnh báo từ `second_opinion` (mô hình phụ phát hiện vật thể nhưng dưới ngưỡng tự động thêm box hoặc lệch IoU với nhãn gốc), `TINY_BOX` biên độ nhỏ, và các mẫu khó phân biệt `truck`/`bus`.
* **Tình trạng hàng đợi người duyệt so với ngân sách:**
  * Hàng đợi cần người duyệt (`07_error_list_v3.csv`) có **38 ảnh**, hoàn toàn **nằm trong ngân sách tối đa 80 ảnh/ngày** (`38 / 80 = 47.5%` ngân sách), **không vượt ngân sách**.
  * Tuy nhiên, do tỷ lệ ảnh cảnh báo chưa duyệt (`18.72%`) vượt ngưỡng tự động phát hành `max_warn_ratio = 10.00%`, cổng quyết định (`gate.py`) đã kích hoạt trạng thái **`Hold`** để yêu cầu con người rà soát 38 ảnh này trước khi đưa vào huấn luyện chính thức.
* **Đây đã là chặn trên (Oracle) của "dữ liệu sạch" chưa?**
  * **Chưa phải chặn trên.** `clean_v1` mới chỉ là dữ liệu **sau xử lý tự động + chưa qua vòng duyệt tay (Human-in-the-Loop)** đối với 38 ảnh đang ở trạng thái `Hold`. Việc vẫn còn 18.72% ảnh nghi ngờ chưa được con người xác nhận (cộng với việc một số mẫu khó bị loại bỏ thay vì sửa nhãn thủ công như tập `oracle`) khiến `clean_v1` chưa đạt tới giới hạn trần của bộ dữ liệu được con người kiểm duyệt 100%.