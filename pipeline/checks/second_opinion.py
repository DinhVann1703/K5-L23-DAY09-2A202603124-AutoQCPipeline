"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    scfg = cfg["second_opinion"]
    conf_thresh = float(scfg["conf"])
    min_area_px = float(scfg["min_area_px"])
    fp_conf = float(scfg["fp_conf"])
    iou_missing = float(scfg["iou_missing"])
    iou_match = float(scfg["iou_match"])
    iou_loose = float(scfg["iou_loose"])
    num_classes = len(ds.classes)

    issues = []

    for img_path in ds.image_files():
        stem = img_path.stem
        if stem not in preds:
            continue
        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue

        img_size = ds.image_size(stem)
        img_w, img_h = img_size if img_size is not None else (0, 0)
        img_preds = preds[stem] or []

        # Lấy các nhãn hợp lệ kèm số dòng gốc (dùng để kiểm tra FALSE_POS)
        valid_labels_with_line = []
        for line_no, text in raw_lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if 0 <= cls_id < num_classes and w > 0 and h > 0:
                valid_labels_with_line.append((line_no, cls_id, (cx, cy, w, h)))

        valid_labels = [(cls_id, box) for _, cls_id, box in valid_labels_with_line]

        # 1. Duyệt dự đoán của model lớn theo đúng thứ tự trong preds[stem]
        for p in img_preds:
            p_cls, p_conf, px, py, pw, ph = int(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[5])
            if p_conf < conf_thresh:
                continue
            area_px = (pw * img_w) * (ph * img_h)
            if area_px < min_area_px:
                continue

            p_box = (px, py, pw, ph)
            cands = []
            for l_cls, l_box in valid_labels:
                iou = iou_xywh(p_box, l_box)
                if iou >= iou_missing:
                    cands.append((iou, l_cls))

            if not cands:
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_MISSING", stem,
                    f"model thấy lớp {p_cls} (conf={p_conf:.2f}) nhưng nhãn không có",
                    extra={"conf": round(p_conf, 4)}
                ))
                continue

            same_cls_ious = [iou for iou, l_cls in cands if l_cls == p_cls]
            if same_cls_ious:
                best_same = max(same_cls_ious)
                if best_same < iou_loose:
                    issues.append(Issue(
                        "second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                        f"box nhãn lớp {p_cls} lệch/lỏng so với model (IoU={best_same:.2f} < {iou_loose})",
                        extra={"conf": round(p_conf, 4), "iou": round(best_same, 4)}
                    ))
                # Nếu best_same >= iou_loose -> nhãn đúng lớp đã phủ vật này -> không cờ
            else:
                best_diff = max(iou for iou, _ in cands)
                if best_diff >= iou_match:
                    issues.append(Issue(
                        "second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                        f"nghi gán nhầm lớp (model thấy lớp {p_cls}, IoU={best_diff:.2f})",
                        extra={"conf": round(p_conf, 4), "iou": round(best_diff, 4)}
                    ))

        # 2. Kiểm tra POSSIBLE_FALSE_POS cho từng dòng nhãn hợp lệ (theo số dòng)
        fp_preds = [
            (float(p[2]), float(p[3]), float(p[4]), float(p[5]))
            for p in img_preds
            if float(p[1]) >= fp_conf
        ]
        for line_no, l_cls, l_box in valid_labels_with_line:
            max_iou = max((iou_xywh(l_box, pb) for pb in fp_preds), default=0.0)
            if max_iou < iou_missing:
                issues.append(Issue(
                    "second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                    f"nhãn lớp {l_cls} không khớp dự đoán nào của model (max_iou={max_iou:.2f})",
                    line=line_no, extra={"iou": round(max_iou, 4)}
                ))

    return issues