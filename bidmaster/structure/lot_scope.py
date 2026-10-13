"""分标/包件作用域识别与包件级字段抽取（P0 范围解析）。

对标 bid-agent-vscode 处理账本的对象归属思想 + BidPilot-AI 的 scope 模型：
  文件级：从文件名/文件开头内容识别"这个文件属于哪个分标/包件"
  表格级：公告的逐包限价表（包号/工程名称/包名称/…/分项限价/最高限价）
          与包件文件的工期表（标包划分/…/开始时间/完成时间）按行解析，
          产出 per-lot 字段——多分标公告不再共用一个"最高限价"。
"""
from __future__ import annotations

import re

from bidmaster.schemas.document import ParsedDocument
from bidmaster.schemas.fields import FieldCandidate, FieldExtraction, empty_extraction
from bidmaster.schemas.evidence import EvidenceStore, make_evidence

# 文件名/标题中的包件名：结算审核包1 / 监造包2 / 包12-15 / 施工A包
_LOT_NAME_RE = re.compile(
    r"(?:结算审核|竣工决算审核|监造|监理|系统调试|科研|工程保险|施工|设计)?包\d{1,2}(?:-\d{1,2})?")

_DATE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月")


def infer_file_scope(file_name: str, blocks: list) -> dict | None:
    """识别一个源文件属于哪个包件。

    优先文件名（结算审核包1新.docx → 结算审核包1），
    其次文件开头的标题块（"浙江特高压交流环网线路工程结算审核包1"）。
    公告/通用文件 → None（全局作用域）。
    """
    m = _LOT_NAME_RE.search(file_name)
    lot_from_name = m.group(0) if m else None
    # 内容扫描：标题块找包件名与其前缀（= 项目/工程名）
    seen = 0
    for b in blocks[:12]:
        t = (b.text or "").strip()
        if not t or t.startswith("[文件"):
            continue  # 跳过合并标记块（其文本含文件名，会提前误匹配且无项目前缀）
        seen += 1
        m = _LOT_NAME_RE.search(t)
        if m and seen <= 6:
            lot = m.group(0)
            proj = t[:m.start()].strip(" 　-—")
            if lot_from_name and _norm_lot(lot) != _norm_lot(lot_from_name):
                continue  # 标题里的包件与文件名不一致，继续找
            return {"lot": lot_from_name or lot,
                    "project": proj if len(proj) >= 6 else ""}
    if lot_from_name:
        return {"lot": lot_from_name, "project": ""}
    return None


def _norm_lot(name: str) -> str:
    return re.sub(r"[ \t]", "", name)


def _find_col(header_cells: list[str], keywords: tuple[str, ...]) -> int | None:
    for ci, h in enumerate(header_cells):
        if any(kw in h for kw in keywords):
            return ci
    return None


_SUMMARY_COLUMNS = {
    "split_no": ("分标编号",),
    "split_name": ("分标名称",),
    "package_count": ("分包数量", "包件数量"),
    "subcontract_allowed": ("是否允许分包", "允许分包"),
    "lot_no": ("包号", "标包号", "包件号", "包件编号"),
    "package_name": ("包名称", "标包名称", "标段名称"),
    "project_name": ("项目名称", "工程名称"),
    "application_no": ("网省采购申请号", "采购申请号", "采购申请编号"),
    "tender_scope": ("招标范围", "服务范围", "工作范围"),
    "site": ("建设地点", "项目地点", "实施地点"),
    "duration": ("工期/服务期", "工期", "服务期", "服务期限", "合同工期"),
    "single_price_limit": ("单项最高限价", "单项限价", "分项最高限价", "分项限价"),
    "package_price_limit": ("包最高限价", "包件最高限价", "包限价", "标包最高限价"),
    "special_qualification": ("资质要求", "资格要求"),
    "special_performance": ("业绩要求", "业绩条件"),
    "special_personnel": ("人员要求", "人员资格要求"),
}


def _header_text(value: str) -> str:
    return re.sub(r"[\s\u3000:：()（）\[\]【】]", "", value or "")


def _column_map(header: list[str]) -> dict[str, int]:
    normalized = [_header_text(cell) for cell in header]
    found: dict[str, int] = {}
    # Narrow headers are matched before broad ones to avoid treating 分标名称 as 包名称.
    for key, aliases in _SUMMARY_COLUMNS.items():
        for ci, cell in enumerate(normalized):
            if any(_header_text(alias) in cell for alias in aliases):
                found[key] = ci
                break
    return found


def _package_range(value: str) -> list[str]:
    """Expand an explicit 包01-包03 row scope; otherwise keep its original key."""
    text = re.sub(r"\s+", "", value or "")
    match = re.fullmatch(r"包0*(\d+)(?:-|~|～|至|到)包?0*(\d+)", text)
    if not match:
        return [text] if text else []
    start, end = int(match.group(1)), int(match.group(2))
    if end < start or end - start > 99:
        return [text]
    width = max((len(part) for part in re.findall(r"\d+", text)), default=1)
    return [f"包{number:0{width}d}" for number in range(start, end + 1)]


def _field_value(value: str, key: str) -> tuple[str, str | None]:
    raw = (value or "").strip()
    if key in {"price_limit", "single_price_limit", "package_price_limit"}:
        from bidmaster.extraction.field_types import _clean_amount
        from bidmaster.extraction.normalize import normalize_amount

        if not raw:
            return "", None
        candidate = raw if "元" in raw or "万" in raw else f"{raw}元"
        if _clean_amount(candidate, key) is None:
            return raw, None
        amount = normalize_amount(candidate)
        if not amount:
            return raw, None
        number = float(amount[0])
        return raw, str(int(number)) if number.is_integer() else str(number)
    return raw, raw or None


def extract_lot_table_fields(parsed: ParsedDocument,
                             store: EvidenceStore) -> dict[str, dict[str, FieldExtraction]]:
    """从公告逐包限价表 / 包件工期表按行解析 per-lot 字段。

    返回 {lot_name: {field_key: FieldExtraction}}，lot 名做归一化关联。
    """
    lot_fields: dict[str, dict[str, FieldExtraction]] = {}

    def _put(lot: str, key: str, value_raw: str, value_norm: str | None,
             conf: float, ev) -> None:
        lot = _norm_lot(lot)
        bucket = lot_fields.setdefault(lot, {})
        f = bucket.get(key) or empty_extraction(key)
        cand = FieldCandidate(value_raw=value_raw, value_normalized=value_norm or "",
                              source="table", confidence=conf,
                              evidence_id=ev.evidence_id, zone="包件表")
        f.candidates.append(cand)
        if f.status != "found" or conf >= f.confidence:
            f.status = "found"
            f.value_raw = value_raw
            f.value_normalized = value_norm
            f.confidence = conf
            f.evidence_ids = [ev.evidence_id]
        bucket[key] = f

    split_rows: dict[str, dict[str, FieldExtraction]] = {}

    for tb in parsed.tables:
        if not tb.rows or len(tb.rows) < 2:
            continue
        header_index = 0
        columns = _column_map(tb.rows[0])
        # Some generated XLSX/Word tables prepend a title row; select the strongest
        # recognizable header among the first four rows.
        for candidate_index, candidate in enumerate(tb.rows[1:min(4, len(tb.rows))], 1):
            candidate_columns = _column_map(candidate)
            if len(candidate_columns) > len(columns):
                header_index, columns = candidate_index, candidate_columns

        start_ci = _find_col(tb.rows[header_index], ("开始时间", "计划开工日期", "计划开始"))
        end_ci = _find_col(tb.rows[header_index], ("完成时间", "计划竣工日期", "计划完成"))
        has_scope = any(k in columns for k in ("lot_no", "package_name", "split_name"))
        if not has_scope:
            continue
        summary_columns = {"split_no", "split_name", "package_count", "subcontract_allowed"}
        package_columns = set(columns) - summary_columns
        if not (package_columns or summary_columns.intersection(columns)
                or start_ci is not None and end_ci is not None):
            continue


        for row_index, row in enumerate(tb.rows[header_index + 1:], header_index + 1):
            cells = [str(c or "").strip() for c in row]
            if not any(cells):
                continue
            def cell_for(key: str) -> str:
                ci = columns.get(key)
                return cells[ci] if ci is not None and ci < len(cells) else ""

            split_name = cell_for("split_name")
            package_key = cell_for("lot_no") or cell_for("package_name") or split_name
            if not package_key:
                continue
            targets = _package_range(package_key)
            ev = store.add(make_evidence(
                kind="table_cell", source="table",
                page_no=(tb.row_pages[row_index] if row_index < len(tb.row_pages)
                         else tb.page_nos[0] if tb.page_nos else 0),
                table_id=tb.table_id, row=row_index,
                snippet=" | ".join(cells)[:200]))

            values = {key: cell_for(key) for key in columns}
            is_split_only = bool(summary_columns.intersection(columns)) and not any(
                values.get(key) for key in ("lot_no", "package_name"))
            destination = split_rows.setdefault(_norm_lot(split_name or package_key), {}) if is_split_only else None

            for key, raw in values.items():
                if not raw:
                    continue
                if is_split_only:
                    value_raw, value_norm = _field_value(raw, key)
                    if value_norm is None:
                        continue
                    f = destination.get(key) or empty_extraction(key)
                    f.candidates.append(FieldCandidate(
                        value_raw=value_raw, value_normalized=value_norm, source="table",
                        confidence=0.95, evidence_id=ev.evidence_id, zone="分标汇总表"))
                    f.status, f.value_raw, f.value_normalized = "found", value_raw, value_norm
                    f.confidence, f.evidence_ids = 0.95, [ev.evidence_id]
                    destination[key] = f
                else:
                    column_index = columns.get(key)
                    header_text = (_header_text(tb.rows[header_index][column_index])
                                   if column_index is not None else "")
                    if key in {"price_limit", "single_price_limit", "package_price_limit"}:
                        unit = "万元" if "万元" in header_text else "元"
                        raw = raw if "元" in raw or "万" in raw else f"{raw}{unit}"
                    for target in targets:
                        target_raw = target if key == "lot_no" else raw
                        value_raw, value_norm = _field_value(target_raw, key)
                        if value_norm is None:
                            continue
                        confidence = 0.95 if key in {"lot_no", "package_name",
                                                     "single_price_limit", "package_price_limit"} else 0.9
                        _put(target, key, value_raw, value_norm, confidence, ev)

            generic_price_ci = next((ci for ci, heading in enumerate(tb.rows[header_index])
                                     if _header_text(heading).startswith("最高限价")
                                     and "单项" not in heading and "包最高" not in heading
                                     and "包件最高" not in heading), None)
            if generic_price_ci is not None and generic_price_ci < len(cells):
                raw = cells[generic_price_ci]
                if raw:
                    heading = _header_text(tb.rows[header_index][generic_price_ci])
                    unit = "万元" if "万元" in heading else "元"
                    raw = raw if "元" in raw or "万" in raw else f"{raw}{unit}"
                    value_raw, value_norm = _field_value(raw, "price_limit")
                    if value_norm:
                        for target in targets:
                            _put(target, "price_limit", value_raw, value_norm, 0.95, ev)

            duration_ci = columns.get("duration")
            if duration_ci is not None and duration_ci < len(cells):
                duration = cells[duration_ci]
                if duration:
                    sm, em = _DATE.search(duration), None
                    range_match = re.search(r"(.{0,30}?)(?:至|到|[-—~～])(.{0,30})", duration)
                    if range_match:
                        sm, em = _DATE.search(range_match.group(1)), _DATE.search(range_match.group(2))
                    if sm and em:
                        normalized = (f"{sm.group(1)}年{int(sm.group(2))}月"
                                      f"至{em.group(1)}年{int(em.group(2))}月")
                    else:
                        normalized = duration
                    for target in targets:
                        _put(target, "duration", duration, normalized, 0.9, ev)

            if start_ci is not None and end_ci is not None and max(start_ci, end_ci) < len(cells):
                sm, em = _DATE.search(cells[start_ci]), _DATE.search(cells[end_ci])
                if sm and em:
                    duration = (f"{sm.group(1)}年{int(sm.group(2))}月"
                                f"至{em.group(1)}年{int(em.group(2))}月")
                    for target in targets:
                        _put(target, "duration", duration, duration, 0.9, ev)

    # Attach summary-table split metadata to each package row that names that split.
    for bucket in lot_fields.values():
        split_field = bucket.get("split_name")
        split_name = split_field.value_raw if split_field else ""
        shared = split_rows.get(_norm_lot(split_name))
        if shared:
            for key, field in shared.items():
                bucket.setdefault(key, field.model_copy(deep=True))
    # Keep split-only rows available for the UI when no package-detail rows exist.
    for split_name, fields in split_rows.items():
        lot_fields.setdefault(split_name, fields)

    return lot_fields


def file_block_ranges(parsed: ParsedDocument) -> list[tuple[int, int, str]]:
    """合并文档中各源文件的块范围 [(start, end, file_name)]（end 不含）。"""
    marks = []
    for i, b in enumerate(parsed.blocks):
        if b.type == "heading" and b.text.startswith("[文件") and "]:" in b.text or \
           (b.type == "heading" and re.match(r"^\[文件\d+:", b.text)):
            marks.append((i, b.text))
    if not marks:
        return [(0, len(parsed.blocks), parsed.file_name)]
    out = []
    for j, (start, label) in enumerate(marks):
        end = marks[j + 1][0] if j + 1 < len(marks) else len(parsed.blocks)
        name = label.split(":", 1)[1].rstrip("]").strip() if ":" in label else label
        out.append((start, end, name))
    return out
