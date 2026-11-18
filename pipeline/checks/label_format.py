"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.  (Script 2 trong slide)  ★★"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    issues = []
    lcfg = cfg["label_format"]
    overflow_tol = float(lcfg["overflow_tol"])
    min_box_px = float(lcfg["min_box_px"])
    max_box_frac = float(lcfg["max_box_frac"])
    dup_box_iou = float(lcfg["dup_box_iou"])
    num_classes = len(ds.classes)

    # Duyệt từng ảnh có file nhãn (read_label_lines trả về None nếu không có file)
    for img_path in ds.image_files():
        stem = img_path.stem
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue

        img_size = ds.image_size(stem)
        seen_boxes: list[tuple[int, float, float, float, float]] = []

        for line_no, text in lines:
            # 1. BAD_FORMAT
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue(
                    "label_format", ERROR, "BAD_FORMAT", stem,
                    f"dòng sai định dạng: {e}", line=line_no
                ))
                continue

            # 2. BAD_CLASS_ID
            if not (0 <= cls_id < num_classes):
                issues.append(Issue(
                    "label_format", ERROR, "BAD_CLASS_ID", stem,
                    f"id lớp {cls_id} ngoài 0..{num_classes - 1}", line=line_no
                ))
                continue

            # 3. BOX_ZERO
            if w <= 0 or h <= 0:
                issues.append(Issue(
                    "label_format", ERROR, "BOX_ZERO", stem,
                    f"kích thước box không hợp lệ (w={w}, h={h})", line=line_no
                ))
                continue

            # 4. BOX_OUT_OF_IMAGE
            left = cx - w / 2.0
            right = cx + w / 2.0
            top = cy - h / 2.0
            bottom = cy + h / 2.0
            overflow = max(0.0, -left, right - 1.0, -top, bottom - 1.0)
            if overflow > overflow_tol:
                issues.append(Issue(
                    "label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                    f"box tràn khỏi ảnh mức {overflow:.4f}",
                    line=line_no, extra={"overflow": round(overflow, 6)}
                ))

            # 5. DUP_BOX (so với các box hợp lệ TRƯỚC ĐÓ cùng lớp)
            curr_box = (cx, cy, w, h)
            is_dup = False
            for prev_cls, pcx, pcy, pw, ph in seen_boxes:
                if prev_cls == cls_id and iou_xywh(curr_box, (pcx, pcy, pw, ph)) > dup_box_iou:
                    is_dup = True
                    break
            if is_dup:
                issues.append(Issue(
                    "label_format", ERROR, "DUP_BOX", stem,
                    f"box trùng lặp với dòng trước đó (cùng lớp {cls_id})", line=line_no
                ))
            seen_boxes.append((cls_id, cx, cy, w, h))

            # 6. BOX_TINY (WARN)
            if img_size is not None:
                img_w, img_h = img_size
                short_side_px = min(w * img_w, h * img_h)
                if short_side_px < min_box_px:
                    issues.append(Issue(
                        "label_format", WARN, "BOX_TINY", stem,
                        f"box quá nhỏ ({short_side_px:.1f}px < {min_box_px}px)", line=line_no
                    ))

            # 7. BOX_HUGE (WARN)
            if w * h > max_box_frac:
                issues.append(Issue(
                    "label_format", WARN, "BOX_HUGE", stem,
                    f"box chiếm diện tích quá lớn ({w * h:.3f} > {max_box_frac})", line=line_no
                ))

    return issues