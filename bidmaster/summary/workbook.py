"""Build a review-ready Excel summary from source-backed TenderBrief results."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_NAVY = "18324B"
_BLUE = "E5EEF6"
_PALE = "F4F7FA"
_AMBER = "FFF2CC"
_LINE = "CFD8E2"
_MISSING = "未提取到，请人工核对原文"
_PRICE_KEYS = {"single_price_limit", "package_price_limit", "price_limit"}


def _lot_aliases(*values: str) -> set[str]:
    aliases = set()
    for value in values:
        compact = "".join(str(value or "").split()).lower()
        if compact:
            aliases.add(compact)
        import re
        for match in re.finditer(r"(?:标包|包|标段)0*(\d+)", compact):
            aliases.add(f"package:{int(match.group(1))}")
    return aliases


def _data(field):
    if field is None:
        return {}
    return field.model_dump(mode="json") if hasattr(field, "model_dump") else field


def _value(fields: dict, key: str) -> tuple[str, str, str]:
    field = _data(fields.get(key))
    if field.get("status") != "found":
        return _MISSING, "未识别", ""
    value = field.get("value_raw") if key in _PRICE_KEYS else (
        field.get("value_normalized") or field.get("value_raw"))
    return str(value or _MISSING), "待人工复核", (field.get("evidence_ids") or [""])[0]


def _safe(value):
    text = "" if value is None else str(value)
    # Prevent untrusted document text from becoming an Excel formula.
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def _style_sheet(ws):
    ws.freeze_panes = "A2"
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0


def _title(ws, row: int, title: str, end_col: int):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=end_col)
    cell = ws.cell(row, 1, _safe(title))
    cell.font = Font(name="Microsoft YaHei", size=14, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor=_NAVY)
    cell.alignment = Alignment(vertical="center")
    ws.row_dimensions[row].height = 28


def _table(ws, row: int, headers: list[str], rows: list[list], *, focus_col: int | None = None) -> int:
    edge = Side(style="thin", color=_LINE)
    for col, text in enumerate(headers, 1):
        cell = ws.cell(row, col, _safe(text))
        cell.font = Font(bold=True, color=_NAVY)
        cell.fill = PatternFill("solid", fgColor=_BLUE)
        cell.border = Border(bottom=edge)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
    for offset, values in enumerate(rows, 1):
        target_row = row + offset
        for col, value in enumerate(values, 1):
            cell = ws.cell(target_row, col, _safe(value))
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = Border(bottom=edge)
            if focus_col == col:
                cell.fill = PatternFill("solid", fgColor=_AMBER)
        ws.row_dimensions[target_row].height = 32
    return row + len(rows) + 1


def build_summary_xlsx(report, selected_lot: str, directories: dict) -> bytes:
    """Return a two-sheet xlsx focused on exactly one user-selected package."""
    lot_fields = (report.lot_fields or {}).get(selected_lot, {})
    global_fields = report.fields or {}
    fields = dict(global_fields)
    fields.update(lot_fields)

    wb = Workbook()
    ws = wb.active
    ws.title = "投标要点汇总表"
    _style_sheet(ws)
    widths = [24, 46, 18, 22, 18]
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(index)].width = width
    _title(ws, 1, f"投标要点汇总表 · 目标标包 {selected_lot}", len(widths))
    ws.cell(2, 1, f"来源文件：{report.file_name}　任务编号：{report.doc_id}")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(widths))
    ws.cell(3, 1, "自动抽取结果供编标前核对；未识别字段请根据原文补录，证据编号可在系统内定位来源。")
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(widths))
    ws.cell(3, 1).alignment = Alignment(wrap_text=True, vertical="top")

    row = 5
    _title(ws, row, "基本信息", len(widths))
    row += 1
    basic_keys = ["project_name", "tender_no", "tenderer", "agency", "bid_deadline"]
    basic_rows = []
    for key in basic_keys:
        field = _data(global_fields.get(key))
        value, status, evidence_id = _value(global_fields, key)
        basic_rows.append([field.get("field_label") or key, value, status,
                           evidence_id, "; ".join(field.get("evidence_ids") or [])])
    row = _table(ws, row, ["字段", "识别内容", "状态", "首条证据", "全部证据编号"], basic_rows)

    row += 1
    _title(ws, row, "分标信息", len(widths))
    row += 1
    split_keys = ["split_no", "split_name", "package_count", "subcontract_allowed"]
    split_rows = []
    for key in split_keys:
        field = _data(fields.get(key))
        value, status, evidence_id = _value(fields, key)
        split_rows.append([field.get("field_label") or key, value, status,
                           evidence_id, "; ".join(field.get("evidence_ids") or [])])
    row = _table(ws, row, ["字段", "识别内容", "状态", "首条证据", "全部证据编号"], split_rows)

    row += 1
    _title(ws, row, "目标包招标需求", len(widths))
    row += 1
    package_keys = ["split_name", "lot_no", "package_name", "project_name", "application_no",
                    "tender_scope", "site", "duration", "single_price_limit", "package_price_limit"]
    package_rows = []
    for key in package_keys:
        field = _data(fields.get(key))
        value, status, evidence_id = _value(fields, key)
        package_rows.append([field.get("field_label") or key, value, status,
                             evidence_id, "; ".join(field.get("evidence_ids") or [])])
    row = _table(ws, row, ["字段", "识别内容", "状态", "首条证据", "全部证据编号"], package_rows)

    row += 1
    _title(ws, row, "专用资格要求", len(widths))
    row += 1
    requirement_keys = ["special_qualification", "special_performance", "special_personnel"]
    requirement_rows = []
    for key in requirement_keys:
        field = _data(fields.get(key))
        value, status, evidence_id = _value(fields, key)
        requirement_rows.append([field.get("field_label") or key, value, status,
                                 evidence_id, "; ".join(field.get("evidence_ids") or [])])
    _table(ws, row, ["要求类别", "识别内容", "状态", "首条证据", "全部证据编号"], requirement_rows)

    directory = wb.create_sheet("投标文件目录")
    _style_sheet(directory)
    for index, width in enumerate([18, 12, 76, 26, 20], 1):
        directory.column_dimensions[get_column_letter(index)].width = width
    _title(directory, 1, "投标文件目录与评分项补充", 5)
    directory.cell(2, 1, "目录候选来自‘投标文件格式’章节；评分项补充项需人工确认后再用于编标。")
    directory.merge_cells(start_row=2, start_column=1, end_row=2, end_column=5)
    row = 4
    for category, label in (("business", "商务文件"), ("technical", "技术文件"), ("price", "价格文件")):
        items = directories.get(category, [])
        _title(directory, row, label, 5)
        row += 1
        values = [[index, item.get("status", "原文目录"), item.get("title", ""),
                   item.get("origin", ""), item.get("evidence_id", "")]
                  for index, item in enumerate(items, 1)] or [["—", "未提取", "未找到目录条目，请人工核对原文", "", ""]]
        row = _table(directory, row, ["序号", "状态", "目录条目", "目录来源", "证据编号"], values)
        row += 1

    score_sheet = wb.create_sheet("评分项")
    _style_sheet(score_sheet)
    for index, width in enumerate([16, 34, 12, 20, 24, 20], 1):
        score_sheet.column_dimensions[get_column_letter(index)].width = width
    _title(score_sheet, 1, f"目标标包评分项 · {selected_lot}", 6)
    scores = []
    selected_split = _value(fields, "split_name")[0]
    selected_package_name = _value(fields, "package_name")[0]
    selected_lot_no = _value(fields, "lot_no")[0]
    selected_aliases = _lot_aliases(selected_lot, selected_lot_no,
                                    selected_package_name, selected_split)
    for score in report.scores or []:
        parsed_rule = score.parsed_rule or {}
        score_lot = str(parsed_rule.get("lot") or "")
        if score_lot and score_lot != "全局/未分包" \
                and not selected_aliases.intersection(_lot_aliases(score_lot)):
            continue
        scores.append([score.category or "待分类", score.name or "", score.max_score or "",
                       score.status or "待复核", score_lot or "全局/未分包",
                       (score.evidence_ids or [""])[0]])
    _table(score_sheet, 2, ["类别", "评分项", "分值", "状态", "所属标包", "证据编号"],
           scores or [["—", "未提取到评分项", "", "未识别", selected_lot, ""]])

    output = BytesIO()
    wb.save(output)
    return output.getvalue()
