"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_PREFIXES = ("DUP_IMAGE_",)
REMOVE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def fix(ds, issues, cfg):
    fixes = []
    err_issues = [iss for iss in issues if iss.severity == ERROR]

    # 1. Thu thập ảnh cần xoá hoàn toàn
    removed_images: set[str] = set()
    for iss in err_issues:
        if iss.code in REMOVE_CODES or any(iss.code.startswith(p) for p in REMOVE_PREFIXES):
            if iss.image not in removed_images:
                removed_images.add(iss.image)
                img_p = ds.image_path(iss.image)
                lbl_p = ds.label_path(iss.image)
                existed = []
                if img_p and img_p.exists():
                    existed.append(img_p.name)
                    img_p.unlink()
                if lbl_p.exists():
                    existed.append(lbl_p.name)
                    lbl_p.unlink()
                fixes.append({
                    "image": iss.image,
                    "line": "",
                    "action": "remove_image",
                    "before": ", ".join(existed) if existed else iss.image,
                    "after": "(đã xoá)",
                })

    # 2. Sửa tên lớp trong data.yaml (chỉ làm 1 lần nếu có BAD_CLASS_NAME)
    if any(iss.code == "BAD_CLASS_NAME" for iss in err_issues):
        before_names = ds.yaml_names()
        data = {}
        if ds.yaml_path.exists():
            data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        data["names"] = list(cfg["classes"])
        ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fixes.append({
            "image": "data.yaml",
            "line": "",
            "action": "rename_classes",
            "before": str(before_names),
            "after": str(list(cfg["classes"])),
        })

    # 3. Xử lý MISSING_LABEL_FILE (không tạo file rỗng, chỉ ghi log chuyển người gán)
    seen_missing: set[str] = set()
    for iss in err_issues:
        if iss.code == "MISSING_LABEL_FILE" and iss.image not in removed_images and iss.image not in seen_missing:
            seen_missing.add(iss.image)
            fixes.append({
                "image": iss.image,
                "line": "",
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })

    # 4. Gom lỗi theo từng file nhãn (bỏ qua ảnh đã bị xoá)
    file_ops: dict[str, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for iss in err_issues:
        if iss.image in removed_images or iss.line is None:
            continue
        if iss.code in DROP_CODES:
            file_ops[iss.image][iss.line].add("drop")
        elif iss.code == "BOX_OUT_OF_IMAGE":
            file_ops[iss.image][iss.line].add("clip")

    for stem in sorted(file_ops.keys()):
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue
        raw_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines = []
        ops_by_line = file_ops[stem]

        for line_no, text in enumerate(raw_lines, 1):
            ops = ops_by_line.get(line_no)
            if not ops:
                new_lines.append(text)
                continue

            # Ưu tiên drop_line nếu dòng vừa có lỗi drop vừa có lỗi clip
            if "drop" in ops:
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": text.strip(),
                    "after": "(đã xoá)",
                })
                continue

            if "clip" in ops:
                try:
                    cls_id, cx, cy, w, h = parse_yolo_line(text)
                except ValueError:
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": text.strip(),
                        "after": "(đã xoá)",
                    })
                    continue

                x1 = max(0.0, min(1.0, cx - w / 2.0))
                y1 = max(0.0, min(1.0, cy - h / 2.0))
                x2 = max(0.0, min(1.0, cx + w / 2.0))
                y2 = max(0.0, min(1.0, cy + h / 2.0))
                nw = x2 - x1
                nh = y2 - y1

                # Nếu sau khi cắt box không còn diện tích -> xoá dòng
                if nw <= 1e-9 or nh <= 1e-9:
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": text.strip(),
                        "after": "(đã xoá)",
                    })
                    continue

                ncx = (x1 + x2) / 2.0
                ncy = (y1 + y2) / 2.0
                clipped_str = f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                new_lines.append(clipped_str)
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "clip_box",
                    "before": text.strip(),
                    "after": clipped_str,
                })

        lbl_p.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

    return fixes