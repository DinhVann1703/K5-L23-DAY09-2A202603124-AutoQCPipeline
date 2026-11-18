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
Chưa chạy; đang huấn luyện trên Google Colab. Sẽ cập nhật `submission/results/comparison.md` khi hoàn tất.

## 6. Quyết định và ghi chú AI
- **Quyết định:** giữ **HOLD**, chưa phát hành `clean_v1` lên production. Gate yêu cầu cảnh báo chưa duyệt dưới 10%, tức tối đa **20/203 ảnh**; cần xử lý ít nhất **18/38 ảnh cảnh báo còn lại**, rồi chạy lại gate. Số ảnh cần duyệt thêm thực tế phụ thuộc kết quả duyệt.
- **AI:** Prompt nêu input/output và schema `Issue` của các module, quy tắc/ngưỡng lấy từ `cfg`, ca biên cần tránh, và giới hạn phạm vi sửa file. Kiểm code bằng cách đối chiếu docstring/`RULES.md`, chạy `pytest -q` (**79 tests**) và so kết quả lô raw với các báo cáo. Một lỗi AI: bản nháp `label_format.py` chỉ duyệt ảnh, bỏ sót nhãn mồ côi; đã sửa để duyệt hợp các stem ảnh và nhãn.
