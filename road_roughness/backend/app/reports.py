"""Excel and PDF report writers."""

import math
from pathlib import Path

import pandas as pd

from .classification import REPORT_COLUMNS, SURFACE_THRESHOLDS


# ---------------- Excel report ----------------
def write_excel_report(df: pd.DataFrame, summary, meta: dict, table_key: str, path: Path, sheet: str):
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    font = Font(name="Arial", size=10)
    bold = Font(name="Arial", size=10, bold=True)
    head_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1C2124")
    thin = Side(style="thin", color="C7CDC9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    cond_style = {"Good": ("C6EFCE", "006100"), "Fair": ("FFEB9C", "9C5700"), "Poor": ("FFC7CE", "9C0006")}

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name=sheet, index=False)
        wb = xw.book
        ws = xw.sheets[sheet]

        widths = [14, 14, 10, 7, 11, 9, 12, 12, 18, 14, 17, 17, 15, 15, 15, 15, 58]
        formats = {1: "0.000", 2: "0.000", 5: "0.00", 6: "0.000",
                   13: "0.00000000", 14: "0.00000000", 15: "0.00000000", 16: "0.00000000"}
        cond_col = REPORT_COLUMNS.index("Drainage Condition:") + 1
        for c in range(1, len(REPORT_COLUMNS) + 1):
            ws.column_dimensions[get_column_letter(c)].width = widths[c - 1]
            h = ws.cell(row=1, column=c)
            h.font, h.fill, h.border = head_font, head_fill, border
            h.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 30
        for r in range(2, ws.max_row + 1):
            for c in range(1, len(REPORT_COLUMNS) + 1):
                cell = ws.cell(row=r, column=c)
                cell.font, cell.border = font, border
                if c in formats:
                    cell.number_format = formats[c]
            cv = ws.cell(row=r, column=cond_col)
            if cv.value in cond_style:
                bg, fg = cond_style[cv.value]
                cv.fill = PatternFill("solid", fgColor=bg)
                cv.font = Font(name="Arial", size=10, bold=True, color=fg)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        # ---- Summary sheet (live formulas over the data sheet) ----
        sm = wb.create_sheet("Summary")
        sm["A1"] = "Road roughness report — summary"
        sm["A1"].font = Font(name="Arial", size=14, bold=True)
        r = 3
        for k, v in meta.items():
            sm.cell(row=r, column=1, value=k).font = bold
            sm.cell(row=r, column=2, value=v).font = font
            r += 1
        r += 1
        hdr = ["Direction", "Lane", "Segments", "Avg RI", "Avg IRI", "Good", "Fair", "Poor"]
        for c, t in enumerate(hdr, 1):
            cell = sm.cell(row=r, column=c, value=t)
            cell.font, cell.fill, cell.border = head_font, head_fill, border
            cell.alignment = Alignment(horizontal="center")
        q = f"'{sheet}'!"
        rng = lambda col: f"{q}${col}:${col}"
        for row in summary:
            r += 1
            d, l = row["Direction"], row["Lane"]
            sm.cell(row=r, column=1, value=d)
            sm.cell(row=r, column=2, value=l)
            if d == "All":
                sm.cell(row=r, column=3, value=f"=COUNTA({rng('A')})-1")
                sm.cell(row=r, column=4, value=f"=IFERROR(AVERAGE({rng('E')}),\"-\")")
                sm.cell(row=r, column=5, value=f"=IFERROR(AVERAGE({rng('F')}),\"-\")")
                for c, cond in ((6, "Good"), (7, "Fair"), (8, "Poor")):
                    sm.cell(row=r, column=c, value=f"=COUNTIF({rng('I')},\"{cond}\")")
            else:
                crit = f"{rng('C')},$A{r},{rng('D')},$B{r}"
                sm.cell(row=r, column=3, value=f"=COUNTIFS({crit})")
                sm.cell(row=r, column=4, value=f"=IFERROR(AVERAGEIFS({rng('E')},{crit}),\"-\")")
                sm.cell(row=r, column=5, value=f"=IFERROR(AVERAGEIFS({rng('F')},{crit}),\"-\")")
                for c, cond in ((6, "Good"), (7, "Fair"), (8, "Poor")):
                    sm.cell(row=r, column=c, value=f"=COUNTIFS({crit},{rng('I')},\"{cond}\")")
            for c in range(1, 9):
                cell = sm.cell(row=r, column=c)
                cell.border = border
                cell.font = bold if d == "All" else font
            sm.cell(row=r, column=4).number_format = "0.00"
            sm.cell(row=r, column=5).number_format = "0.000"
        r += 1
        sm.cell(row=r, column=1,
                value=f"Counts and averages are formulas over the {sheet} sheet.").font = \
            Font(name="Arial", size=9, italic=True, color="56616A")

        r += 2
        sm.cell(row=r, column=1, value=f"Classification used ({meta['Pavement']})").font = bold
        r += 1
        for c, t in enumerate(["Condition", "RI band", "IRI band"], 1):
            cell = sm.cell(row=r, column=c, value=t)
            cell.font, cell.fill, cell.border = head_font, head_fill, border
        th = SURFACE_THRESHOLDS[table_key]
        for (_, rb, cond), (_, ib, _) in zip(th["RI"], th["IRI"]):
            r += 1
            for c, v in enumerate([cond, rb, ib], 1):
                cell = sm.cell(row=r, column=c, value=v)
                cell.font, cell.border = font, border
        for col, w in zip("ABCDEFGH", [24, 44, 11, 11, 11, 9, 9, 9]):
            sm.column_dimensions[col].width = w
        wb.calculation.fullCalcOnLoad = True


# ---------------- PDF report ----------------
def write_pdf_report(df: pd.DataFrame, summary, meta: dict, table_key: str, path: Path, title: str):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    asphalt = colors.HexColor("#1C2124")
    rule = colors.HexColor("#C7CDC9")
    zebra = colors.HexColor("#F3F4F2")
    cond_bg = {"Good": colors.HexColor("#C6EFCE"), "Fair": colors.HexColor("#FFEB9C"),
               "Poor": colors.HexColor("#FFC7CE")}

    page = landscape(A3)
    margin = 12 * mm
    doc = SimpleDocTemplate(str(path), pagesize=page, leftMargin=margin, rightMargin=margin,
                            topMargin=14 * mm, bottomMargin=14 * mm, title=title,
                            author="Road Roughness Platform")
    s_title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=17, leading=21)
    s_h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceAfter=4)
    s_meta = ParagraphStyle("m", fontName="Helvetica", fontSize=8.5, leading=11)
    s_cell = ParagraphStyle("c", fontName="Helvetica", fontSize=6.8, leading=8.2)
    s_head = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=6.8, leading=8.2,
                            textColor=colors.white, alignment=TA_CENTER)

    story = [Paragraph(title, s_title), Spacer(1, 6)]

    items = list(meta.items())
    half = math.ceil(len(items) / 2)
    left, right = items[:half], items[half:] + [("", "")] * (half - len(items[half:]))
    meta_rows = [[Paragraph(f"<b>{a}</b>", s_meta), Paragraph(str(b), s_meta),
                  Paragraph(f"<b>{c}</b>", s_meta), Paragraph(str(d), s_meta)]
                 for (a, b), (c, d) in zip(left, right)]
    mt = Table(meta_rows, colWidths=[110, 330, 110, 330], hAlign="LEFT")
    mt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("LINEBELOW", (0, -1), (-1, -1), 0.6, asphalt)]))
    story += [mt, Spacer(1, 10)]

    # summary + legend side by side
    s_hdr = ["Direction", "Lane", "Segments", "Avg RI", "Avg IRI", "Good", "Fair", "Poor"]
    s_rows = [s_hdr] + [[r["Direction"], r["Lane"], r["Segments"], f"{r['Avg RI']:.2f}",
                         f"{r['Avg IRI']:.3f}", r["Good"], r["Fair"], r["Poor"]] for r in summary]
    st = Table(s_rows, colWidths=[52, 40, 52, 56, 52, 40, 40, 40], hAlign="LEFT")
    st_style = [("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                ("BACKGROUND", (0, 0), (-1, 0), asphalt), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, rule), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 7.5),
                ("BACKGROUND", (5, 1), (5, -1), cond_bg["Good"]),
                ("BACKGROUND", (6, 1), (6, -1), cond_bg["Fair"]),
                ("BACKGROUND", (7, 1), (7, -1), cond_bg["Poor"])]
    st.setStyle(TableStyle(st_style))

    th = SURFACE_THRESHOLDS[table_key]
    lg_rows = [["Condition", "RI band", "IRI band"]] + \
              [[cond, rb, ib] for (_, rb, cond), (_, ib, _) in zip(th["RI"], th["IRI"])]
    lg = Table(lg_rows, colWidths=[56, 64, 64], hAlign="LEFT")
    lg.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
                            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                            ("BACKGROUND", (0, 0), (-1, 0), asphalt),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.3, rule),
                            ("BACKGROUND", (0, 1), (0, 1), cond_bg["Good"]),
                            ("BACKGROUND", (0, 2), (0, 2), cond_bg["Fair"]),
                            ("BACKGROUND", (0, 3), (0, 3), cond_bg["Poor"])]))
    pair = Table([[Paragraph("Summary by lane", s_h2), "",
                   Paragraph(f"Classification ({meta['Pavement']})", s_h2)],
                  [st, "", lg]], colWidths=[400, 30, 200], hAlign="LEFT")
    pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [pair, Spacer(1, 12), Paragraph(f"{meta['Section length']} roughness", s_h2)]

    def fmt(v, nd):
        return "-" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{float(v):.{nd}f}"

    header = [Paragraph(c.replace("_", " ").strip(), s_head) for c in REPORT_COLUMNS]
    data = [header]
    for rec in df.to_dict("records"):
        data.append([
            fmt(rec["Chainage_Start"], 3), fmt(rec["Chainage_End"], 3), rec["Direction"], rec["Lane"],
            fmt(rec["RI"], 2), fmt(rec["IRI"], 3), rec["IRI_Index"], rec["RI_Index"],
            rec["Drainage Condition:"], rec["Carriage Type "],
            rec["Survey_Date_Start"], rec["Survey_Date_End"],
            fmt(rec["From Latitude"], 8), fmt(rec["From Longitude"], 8),
            fmt(rec["To Latitude"], 8), fmt(rec["To Longitude"], 8),
            Paragraph(str(rec["Roughness_Status"]), s_cell),
        ])
    base_w = [44, 44, 42, 28, 44, 36, 50, 54, 54, 52, 54, 54, 58, 58, 58, 58, 192]
    avail = page[0] - 2 * margin
    col_w = [w * avail / sum(base_w) for w in base_w]
    t = Table(data, colWidths=col_w, repeatRows=1)
    ts = [("FONT", (0, 1), (-1, -1), "Helvetica", 6.8),
          ("BACKGROUND", (0, 0), (-1, 0), asphalt),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("GRID", (0, 0), (-1, -1), 0.25, rule),
          ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, zebra]),
          ("ALIGN", (0, 1), (1, -1), "RIGHT"), ("ALIGN", (4, 1), (5, -1), "RIGHT"),
          ("ALIGN", (12, 1), (15, -1), "RIGHT"),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    ci = REPORT_COLUMNS.index("Drainage Condition:")
    for i, rec in enumerate(df.to_dict("records"), start=1):
        bg = cond_bg.get(rec["Drainage Condition:"])
        if bg is not None:
            ts += [("BACKGROUND", (ci, i), (ci, i), bg), ("FONT", (ci, i), (ci, i), "Helvetica-Bold", 6.8)]
    t.setStyle(TableStyle(ts))
    story.append(t)

    footer_left = f"{meta['Project']}  |  {meta['Pavement']}  |  {meta['Road direction']}"

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#56616A"))
        canvas.drawString(margin, 8 * mm, footer_left)
        canvas.drawRightString(page[0] - margin, 8 * mm, f"Page {doc_.page}  |  Generated {meta['Generated']}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
