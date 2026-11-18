# Báo cáo Day 09 — Bùi Lê Đình Văn, 2A202603124

## 1. Kết luận trước
Pipeline kết luận **HOLD** (mã thoát `10`). Lô có **224 ảnh**; intake loại **21/224**, còn **203 ảnh** vào dataset. Không còn lỗi bắt buộc (`0 ERROR`), nhưng vẫn có **38/203 ảnh cảnh báo chưa được duyệt (18,72%)**, cao hơn ngưỡng **10%**.

## 2. Lỗi và phân việc
`02_error_list_v1` ghi nhận 57 lỗi bắt buộc: 21 lỗi intake tương ứng 21 ảnh bị loại và 36 lỗi trên lô 203 ảnh còn lại; các cảnh báo được thống kê riêng.

| Mã lỗi | Số lượng | Ai sửa | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` / `DUP_IMAGE_NEAR` | 8 / 3 ảnh | Máy | Loại ảnh trùng byte / gần trùng (pHash). |
| `LEAK_TEST` | 5 ảnh | Máy | Loại ảnh trùng kho test/val để tránh rò rỉ. |
| `BAD_SIZE` / `CORRUPT_IMAGE` | 3 / 2 ảnh | Máy | Ảnh quá nhỏ hoặc không đọc được nên không thể dùng. |
| `MISSING_LABEL_FILE` | 6 ảnh | Người | Cần gán nhãn; máy không tự tạo nhãn. |
| `BAD_CLASS_ID` / `BAD_CLASS_NAME` | 6 dòng / 2 tên lớp | Máy | Xóa ID ngoài miền và chuẩn hóa tên lớp theo cấu hình. |
| `BAD_FORMAT` / `BOX_ZERO` | 3 / 4 dòng | Máy | Xóa dòng không đúng định dạng hoặc box có kích thước bằng 0. |
| `BOX_OUT_OF_IMAGE` / `DUP_BOX` | 8 / 7 dòng | Máy | Cắt box về biên ảnh; xóa box trùng cùng lớp. |
| `EMPTY_LABEL` | 12 ảnh | Người | Phân biệt ảnh nền thật với ảnh bị thiếu nhãn. |
| `BOX_TINY` / `BOX_HUGE` | 6 dòng / 3 dòng | Người | Xác nhận box nhỏ hoặc chiếm gần toàn ảnh có hợp lệ không. |
| `CLASS_RARE` | 4 lớp rác | Hệ thống / máy | Cảnh báo phát sinh từ ID sai; xử lý bằng sửa ID trước khi thống kê lại. |
| `POSSIBLE_MISSING` / `POSSIBLE_LOOSE_BOX` | 53 / 28 cảnh báo | Người | Đối chiếu vật thể model phát hiện và kiểm tra box có ôm sát không. |
| `POSSIBLE_FALSE_POS` / `POSSIBLE_WRONG_CLASS` | 25 / 18 cảnh báo | Người | Xác nhận nhãn thừa hoặc lớp nhãn khác dự đoán của model. |

Queue ưu tiên theo tổng trọng số rủi ro và độ tin cậy model. `img_0020` đứng đầu (`priority=11.524`) vì có đồng thời `FIXED_DROP_LINE`, `POSSIBLE_MISSING`, `POSSIBLE_WRONG_CLASS`; sáu ảnh `NEEDS_LABEL` tiếp theo có điểm `10.0`. Với ngân sách **80/125 ảnh**, đã duyệt 6 ảnh thiếu nhãn và 74 ảnh còn lại theo thứ tự ưu tiên; còn 45 ảnh trong queue chưa duyệt. Kết quả cuối vẫn có **38/203 ảnh cảnh báo chưa duyệt**.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu → chọn | Precision / Recall (trước → sau) | Đánh đổi |
|---|---|---|---|
| `duplicates.phash_dist` | `2 → 8` | `DUP_IMAGE_NEAR`: `1.00/0.50 → 1.00/0.67` (F1 `0.67 → 0.80`) | Bắt thêm near-duplicate trên calib mà precision vẫn `1.00`; chọn 8 thận trọng vì calib chỉ có 6 ca near-duplicate. |
| `second_opinion.conf` | `0.25 → 0.6` | `MISSING`: `0.50/1.00 → 0.57/1.00`; `WRONG_CLASS`: `0.56/0.83 → 0.62/0.83` | Precision tăng mà recall hai nhóm không giảm ở ngưỡng 0.6; ở 0.7, recall `MISSING` giảm còn `0.875`. |

Calib chỉ có **39 ảnh**; với `DUP_IMAGE_NEAR`, 8 chỉ bắt được **4/6 ca (recall 0.67)**. Không nên coi sweep nhỏ là bảo đảm trên dữ liệu thật. Ở raw, intake ghi nhận ba near-duplicate với pHash `0, 0, 6` (`img_0076`, `img_0143`, `img_0223`), nên cả ba đều được bắt ở ngưỡng 8. Ngưỡng rộng hơn có thể tăng rủi ro gộp nhầm ảnh tương tự; dữ liệu hiện có không chứng minh đã xảy ra false positive.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**Gate:** chạy với `--budget 0` cho kết quả **REWORK**, còn **6 ERROR**, duyệt `0/80` ảnh và `exported=null` trong `work/rep_nb/08_summary.json` (mã thoát `20`). Dataset không được xuất; sáu ảnh thiếu nhãn vẫn cần người xử lý.

**Điểm mù:**
1. **Trùng ảnh sau biến đổi mạnh:** pHash đã bắt ba cặp gần trùng nhẹ có khoảng cách `0, 0, 6`; phép so khớp với ngưỡng 8 không bảo đảm bắt ảnh bị crop sâu, xoay mạnh hoặc lật.
2. **Box lỏng sát ngưỡng:** `iou_loose=0.5`; box cùng lớp có IoU từ 0.5 trở lên không bị gắn `POSSIBLE_LOOSE_BOX`. Trong v1, `img_0082` có IoU `0.48` nên bị cảnh báo sát ngưỡng—các box ở phía trên ngưỡng có thể lọt qua.
3. **Model bất đồng không đồng nghĩa nhãn sai:** cảnh báo second-opinion dựa vào `yolo26l` và các ngưỡng confidence/IoU; nếu model cũng bỏ sót hoặc phân loại sai, pipeline không thể tự xác định nhãn chuẩn thay cho người.

## 5. Train: raw vs clean (tùy chọn)
Thí nghiệm huấn luyện mô hình **YOLO26n** (`epochs=20`, `imgsz=640`, `batch=16`, 2 seed `0` và `1`) trên GPU Tesla T4 (Google Colab), đánh giá trên cùng tập `data/gold_val` (40 ảnh) và `data/test` (100 ảnh nhãn người):

| Biến thể | Ảnh khai báo | Ảnh thực train (Ultralytics) | mAP50 (TB ± std) | mAP50-95 (TB ± std) | Precision (TB ± std) | Recall (TB ± std) |
|---|---:|---:|---:|---:|---:|---:|
| `raw` | 224 | 213 *(bỏ 11 corrupt)* | `0.726 ± 0.000` | `0.512 ± 0.004` | `0.764 ± 0.061` | `0.649 ± 0.028` |
| `clean` | 203 | 203 *(0 corrupt)* | `0.699 ± 0.025` | `0.486 ± 0.013` | `0.796 ± 0.050` | `0.596 ± 0.049` |

* **Nhận xét chính:**
  * **Chất lượng & Độ chính xác (`Precision`):** `clean` đạt **203/203 ảnh sạch (`0 corrupt`)** (giảm số ảnh background rỗng từ 19 xuống 4 nhờ `autofix`), giúp **Precision tăng từ `0.764` lên `0.796` (+3.2%)** và cải thiện AP50 trên 2 lớp chủ lực là **`person`** (`0.8221` $\rightarrow$ `0.8239`, riêng seed 0 đạt `0.8341`) và **`car`** (`0.7375` $\rightarrow$ `0.7407`, riêng seed 1 đạt `0.7716`).
  * **Lý giải chênh lệch mAP50 (`-0.027`):** Biên độ chênh lệch nằm đúng trong mức dao động tự nhiên giữa 2 seed của `clean` ($\pm 0.025$). Đồng thời, điểm `raw` (`0.726`) bị thổi phồng giả tạo do chứa các ảnh trùng lặp/rò rỉ trực tiếp với tập đánh giá (`LEAK_TEST`), trong khi `clean` đã loại bỏ hoàn toàn rò rỉ và đang ở trạng thái **`Hold`** (`38/203` ảnh cảnh báo nằm trong ngân sách duyệt `38/80`).
  * Chi tiết đầy đủ từng seed và giải đáp 5 câu hỏi phân tích được trình bày tại [`submission/results/ANALYSIS.md`](results/ANALYSIS.md) cùng biểu đồ [`submission/results/comparison.png`](results/comparison.png).
## 6. Quyết định và ghi chú AI
- **Quyết định:** giữ **HOLD**, chưa phát hành `clean_v1` lên production. Gate yêu cầu cảnh báo chưa duyệt dưới 10%, tức tối đa **20/203 ảnh**; cần xử lý ít nhất **18/38 ảnh cảnh báo còn lại**, rồi chạy lại gate. Số ảnh cần duyệt thêm thực tế phụ thuộc kết quả duyệt.
- **AI:** Prompt nêu input/output và schema `Issue` của các module, quy tắc/ngưỡng lấy từ `cfg`, ca biên cần tránh, và giới hạn phạm vi sửa file. Kiểm code bằng cách đối chiếu docstring/`RULES.md`, chạy `pytest -q` (**79 tests**) và so kết quả lô raw với các báo cáo. Một lỗi AI: bản nháp `label_format.py` chỉ duyệt ảnh, bỏ sót nhãn mồ côi; đã sửa để duyệt hợp các stem ảnh và nhãn.
* **Bonus (`LEAK_TEST` Ablation):** Tách riêng 5 ảnh rò rỉ (`test_009`, `test_033`, `test_039`, `test_044`, `test_085`) khỏi 95 ảnh `test_unseen` cho thấy `raw_seed0` bị học vẹt nhóm ảnh rò rỉ với Precision cực đoan (`0.9567`), trong khi `clean_seed0` dù không thấy 5 ảnh này vẫn đạt mAP50-95 cao hơn (`0.5225` vs `0.5054`) và giữ vững Precision vượt trội (`0.8254` vs `0.8007`) trên tập `test_unseen`.