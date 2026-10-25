"""Reference-layout invoice output. FBR acceptance is never inferred from printing."""
import io
import datetime
from typing import Optional, Any
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import KeepTogether, HRFlowable
from backend.app.models.invoice import Invoice
from html import escape
from pathlib import Path
from decimal import Decimal
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, LongTable
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget

PAGE = (1080, 841.68)
FOOTER = 'In the above invoices, "E" denotes that the invoice has been edited, whereas "C" indicates that the invoice has been cancelled.'

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.states = []
    def showPage(self):
        self.states.append(dict(self.__dict__))
        self._startPage()
    def save(self):
        count = len(self.states)
        for state in self.states:
            self.__dict__.update(state)
            self.setFont("Helvetica", 7)
            self.drawString(28, 22, FOOTER)
            self.drawRightString(PAGE[0]-28, 22, f"Page {self._pageNumber} of {count}")
            super().showPage()
        super().save()

class PDFInvoiceGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _init_custom_styles(self):
        self.primary_color = colors.HexColor("#0F172A")    # Slate 900
        self.accent_color = colors.HexColor("#2563EB")     # Blue 600
        self.warning_color = colors.HexColor("#D97706")    # Amber 600
        self.border_color = colors.HexColor("#E2E8F0")     # Slate 200
        self.bg_light = colors.HexColor("#F8FAFC")         # Slate 50

        # Normal text style
        self.styles.add(ParagraphStyle(
            name="InvNormal",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#334155")
        ))
        self.styles.add(ParagraphStyle(
            name="InvNormalBold",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=self.primary_color
        ))
        self.styles.add(ParagraphStyle(
            name="InvTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=self.primary_color
        ))
        self.styles.add(ParagraphStyle(
            name="InvSubtitle",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=self.accent_color
        ))
        self.styles.add(ParagraphStyle(
            name="InvSmall",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#64748B")
        ))
        self.styles.add(ParagraphStyle(
            name="InvTableHeader",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=1 # Center
        ))
        self.styles.add(ParagraphStyle(
            name="InvTableCell",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#1E293B")
        ))
        self.styles.add(ParagraphStyle(
            name="InvTableCellBold",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#0F172A")
        ))
        self.styles.add(ParagraphStyle(
            name="InvTableCellRight",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#1E293B"),
            alignment=2 # Right
        ))
        self.styles.add(ParagraphStyle(
            name="DemoBannerText",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#991B1B"),
            alignment=1 # Center
        ))
        self.styles.add(ParagraphStyle(
            name="InvLogoBadge",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
        ))
        self.styles.add(ParagraphStyle(
            name="InvLogoBadgeRight",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#A7F3D0"),
            alignment=2 # Right
        ))

    def _build_qr_code(self, qr_text, size=65):
        qr = QrCodeWidget(qr_text)
        x, y, right, top = qr.getBounds()
        d = Drawing(size, size, transform=[size/(right-x),0,0,size/(top-y),0,0])
        d.add(qr)
        return d

    def generate(self, invoice, organization_name=None, hs_descriptions=None, qr_payload=None):
        out = io.BytesIO()
        doc = SimpleDocTemplate(out, pagesize=PAGE, leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=42,
            title=f"Invoice {invoice.invoice_number}", author=organization_name or invoice.seller_name)
        cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=6.5, leading=8.8, wordWrap="CJK")
        header = ParagraphStyle("header", parent=cell, fontName="Helvetica-Bold", fontSize=6.7)
        meta = ParagraphStyle("meta", parent=cell, fontSize=9, leading=14)
        title = ParagraphStyle("title", parent=meta, fontName="Helvetica-Bold", fontSize=16, leading=20)
        def para(v, style=cell): return Paragraph(escape(str(v if v is not None else "")), style)
        def amount(v): return f"{Decimal(str(v or 0)):,.2f}"
        accepted = invoice.fbr_status == "VALID" and bool(invoice.fbr_invoice_number)
        simulated = bool(invoice.fbr_is_simulated or invoice.fbr_environment == "DEMO" or invoice.fbr_provider == "MOCK")
        status = "Valid" if accepted and not simulated else "DEMO / SIMULATED" if simulated else "DRAFT / NOT FBR ACCEPTED"
        env = (invoice.fbr_environment or "").upper()
        story=[]
        logo = Path(__file__).resolve().parents[1]/"assets"/"fbr_logo.png"
        branding = Image(str(logo), width=65, height=65, mask='auto') if logo.exists() else para("FBR Digital Invoicing", header)
        qr = self._build_qr_code(qr_payload or invoice.fbr_invoice_number) if accepted and not simulated else para("", cell)
        top=Table([[para((organization_name or invoice.seller_name or "").upper(),title), branding, qr]], colWidths=[864,80,80])
        top.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(-1,-1),'RIGHT')]))
        story += [top, Spacer(1,20)]
        if not accepted or simulated or env == "SANDBOX":
            label = "SANDBOX TEST INVOICE - NOT A PRODUCTION TAX INVOICE" if env == "SANDBOX" and not simulated else status
            story += [para(label, ParagraphStyle("notice",parent=meta,fontName='Helvetica-Bold',textColor=colors.HexColor('#9a3412'))),Spacer(1,8)]
        date = invoice.invoice_date
        insertion = invoice.fbr_submission_date
        from backend.app.core.fbr_taxpayer import normalize_seller_tax_id
        def taxid(v):
            try: return normalize_seller_tax_id(v) or "Unregistered"
            except ValueError: return str(v or "Unregistered")
        seller=["Seller Information",f"Business Name: {invoice.seller_name}",f"Registration No.: {taxid(invoice.seller_ntn)}",f"Province: {invoice.seller_province}",f"Source Invoice No.: {invoice.invoice_number}"]
        buyer=["Buyer Information",f"Business Name: {invoice.buyer_name}",f"Registration No.: {taxid(invoice.buyer_ntn or invoice.buyer_cnic)}",f"Province: {invoice.buyer_province}"]
        summary=["Invoice Summary",f"FBR Invoice No.: {invoice.fbr_invoice_number if accepted else 'Not assigned'}",f"Invoice Date: {date.strftime('%d-%b-%Y') if date else ''}",f"Invoice Type: {'Debit Note' if 'DEBIT' in str(invoice.invoice_type).upper() else 'Sale Invoice'}",f"Tax Period: {date.strftime('%Y%m') if date else ''}",f"Insertion Date: {insertion.strftime('%d-%b-%Y %I:%M %p') if insertion else 'Not recorded'}",f"Status: {status}"]
        metadata=Table([[[para(s,meta) for s in seller],[para(s,meta) for s in buyer],[para(s,meta) for s in summary]]],colWidths=[350,350,324])
        metadata.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0)]))
        story += [metadata, Spacer(1,24)]
        columns=['Sr. No.','HS Code','HS Code Description','Product Description','Sales Type','Quantity','UoM','Rate','Sales Value','Retail Price','Sales Tax','Extra Tax','Further Tax','FED','ST WHT','Discount','SRO / Schedule No.','SRO Item Sr. No.','Petroleum Levy On','Status']
        weights=[2.5,5,11,11,7,3,4,3.5,5,4.5,4,4,4,3,4,4,6,4,4,3]
        widths=[w/sum(weights)*1024 for w in weights]
        rows=[[para(c,header) for c in columns]]
        keys=['taxable_amount','fixed_notified_value_or_retail_price','tax_amount','extra_tax','further_tax','fed_payable','sales_tax_withheld_at_source','discount']
        totals=[Decimal('0') for _ in keys]
        from backend.app.core.fbr_hs_code import normalize_hs_code
        for idx,item in enumerate(invoice.items,1):
            values=[getattr(item,k,None) or 0 for k in keys]
            totals=[t+Decimal(str(v)) for t,v in zip(totals,values)]
            code=normalize_hs_code(item.hs_code)
            data=[idx,code,(hs_descriptions or {}).get(code,''),item.description,item.sale_type,item.quantity,item.uom,item.rate_desc or f"{item.tax_rate}%",*[amount(v) for v in values],item.sro_reference or '',item.sro_item_serial_no or '',getattr(item,'petroleum_levy', '') or '', 'Valid' if accepted and not simulated else '']
            rows.append([para(v) for v in data])
        rows.append([para('') for _ in range(8)]+[para(amount(t),header) for t in totals]+[para('') for _ in range(4)])
        rows[-1][7]=para('Total:',header)
        table=LongTable(rows,colWidths=widths,repeatRows=1,hAlign='LEFT',splitByRow=1,splitInRow=1)
        table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#b8bec5')),('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f4f6f8')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
        story += [table,Spacer(1,12),para(f"Grand Total (PKR): {amount(invoice.grand_total)}",ParagraphStyle('total',parent=meta,fontName='Helvetica-Bold',alignment=2))]
        if accepted and not simulated:
            story += [para('QR: FBR response data' if qr_payload else 'QR: invoice reference only; no local verification signature is asserted.',cell)]
        doc.build(story,canvasmaker=NumberedCanvas)
        return out.getvalue()

    def generate_note(
        self,
        note: Any,
        note_type: str = "CREDIT_NOTE",
        original_invoice: Optional[Invoice] = None,
        taxpayer: Optional[Any] = None,
    ) -> bytes:
        """Generates a legal Pakistan Tax Credit Note or Debit Note PDF."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
        )
        is_credit = "CREDIT" in note_type.upper()
        doc_title = "TAX CREDIT NOTE" if is_credit else "TAX DEBIT NOTE"
        note_num = getattr(note, "credit_note_number", None) or getattr(note, "debit_note_number", "NOTE-001")
        is_demo = bool(getattr(note, "fbr_is_simulated", True) or getattr(note, "fbr_environment", "DEMO") == "DEMO")

        story = []

        # 0. Official PRAL / FBR Digital Invoicing System Badge (PRAL v1.12 Section 4)
        logo_badge_data = [[
            Paragraph(f"🏛️ <b>FEDERAL BOARD OF REVENUE</b> &nbsp;|&nbsp; DIGITAL INVOICING SYSTEM (PRAL)", self.styles["InvLogoBadge"]),
            Paragraph(f"<b>PRAL CERTIFIED {doc_title}</b>", self.styles["InvLogoBadgeRight"])
        ]]
        logo_badge_table = Table(logo_badge_data, colWidths=[120 * mm, 66 * mm])
        logo_badge_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#065F46")), # Emerald 800
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(logo_badge_table)
        story.append(Spacer(1, 2 * mm))

        # 1. Warning banner if DEMO
        if is_demo:
            demo_banner_data = [[
                Paragraph(
                    "<b>*** SIMULATED ENVIRONMENT / DEMO COMPLIANCE DOCUMENT ***</b><br/>"
                    "<font size='6.5'>This is a mock note generated for testing and demonstration. "
                    "Not valid for official fiscal tax deduction or input tax credit adjustment with FBR.</font>",
                    self.styles["InvSmall"]
                )
            ]]
            demo_banner = Table(demo_banner_data, colWidths=[186 * mm])
            demo_banner.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#92400E")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 1, self.warning_color),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(demo_banner)
            story.append(Spacer(1, 3 * mm))

        # 2. Header
        seller_name = taxpayer.legal_name if taxpayer else (original_invoice.seller_name if original_invoice else "FBR Taxpayer")
        seller_ntn = taxpayer.ntn if taxpayer else (original_invoice.seller_ntn if original_invoice else "N/A")
        seller_strn = taxpayer.strn if taxpayer else (original_invoice.seller_strn if original_invoice else "N/A")
        seller_addr = taxpayer.address if taxpayer else (original_invoice.seller_branch_code if original_invoice else "Pakistan")

        supplier_info = (
            f"<b>{seller_name}</b><br/>"
            f"NTN: {seller_ntn} | STRN: {seller_strn or 'N/A'}<br/>"
            f"Address: {seller_addr}"
        )

        note_date_val = getattr(note, "note_date", datetime.datetime.now(datetime.timezone.utc))
        if isinstance(note_date_val, datetime.datetime):
            date_str = note_date_val.strftime("%d-%b-%Y")
        else:
            date_str = str(note_date_val)[:10]

        note_meta = (
            f"<font size='14' color='{self.primary_color.hexval()}'><b>{doc_title}</b></font><br/>"
            f"Note #: <b>{note_num}</b><br/>"
            f"Date: <b>{date_str}</b><br/>"
            f"Status: <b>{note.status}</b>"
        )

        header_table = Table([[Paragraph(supplier_info, self.styles["InvNormal"]), Paragraph(note_meta, self.styles["InvNormal"])]], colWidths=[110 * mm, 76 * mm])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 2 * mm))
        story.append(HRFlowable(width="100%", thickness=1, color=self.border_color, spaceAfter=3 * mm))

        # 3. Reconciliation Reference Box
        orig_fbr = (original_invoice.fbr_invoice_number if original_invoice else None) or "N/A"
        orig_date = (original_invoice.invoice_date.strftime("%d-%b-%Y") if (original_invoice and original_invoice.invoice_date) else "N/A")
        buyer_name = note.buyer_name or (original_invoice.buyer_name if original_invoice else "N/A")
        buyer_ntn = note.buyer_ntn or (original_invoice.buyer_ntn if original_invoice else "N/A")

        reconciliation_info = (
            f"<b>ORIGINAL INVOICE REFERENCE & RECONCILIATION:</b><br/>"
            f"Original Invoice #: <b>{note.original_invoice_number}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Date: {orig_date}<br/>"
            f"Original FBR Fiscal Ref: <b>{orig_fbr}</b><br/>"
            f"Reason for Adjustment: <b>{note.reason}</b>"
        )

        buyer_info = (
            f"<b>BUYER / RECIPIENT:</b><br/>"
            f"<b>{buyer_name}</b><br/>"
            f"NTN: {buyer_ntn or 'N/A'}"
        )

        meta_table = Table([[Paragraph(buyer_info, self.styles["InvNormal"]), Paragraph(reconciliation_info, self.styles["InvNormal"])]], colWidths=[80 * mm, 106 * mm])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.bg_light),
            ("BOX", (0, 0), (-1, -1), 0.5, self.border_color),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 4 * mm))

        # 4. Tax Adjustment Table
        table_data = [
            [
                Paragraph("<b>Description / Tax Adjustment</b>", self.styles["InvTableHeader"]),
                Paragraph("<b>Taxable Amount</b>", self.styles["InvTableHeader"]),
                Paragraph("<b>Sales Tax (Adjustment)</b>", self.styles["InvTableHeader"]),
                Paragraph("<b>Total Adjustment Amount</b>", self.styles["InvTableHeader"]),
            ],
            [
                Paragraph(f"Tax adjustment for {doc_title.lower()} regarding {note.reason}", self.styles["InvTableCell"]),
                Paragraph(f"PKR {float(note.taxable_amount):,.2f}", self.styles["InvTableCellRight"]),
                Paragraph(f"PKR {float(note.tax_amount):,.2f}", self.styles["InvTableCellRight"]),
                Paragraph(f"<b>PKR {float(note.grand_total):,.2f}</b>", self.styles["InvTableCellRight"]),
            ]
        ]
        adj_table = Table(table_data, colWidths=[80 * mm, 35 * mm, 35 * mm, 36 * mm])
        adj_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.primary_color),
            ("GRID", (0, 0), (-1, -1), 0.5, self.border_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(adj_table)
        story.append(Spacer(1, 6 * mm))

        # 5. QR Code & FBR Status Block
        qr_data = getattr(note, "fbr_qr_data", None) or f"FBR-NOTE|NUM:{note_num}|ORIG:{note.original_invoice_number}|TOT:{note.grand_total}|TAX:{note.tax_amount}"
        qr_drawing = self._build_qr_code(qr_data, size=1.0 * inch)

        fbr_note_text = (
            f"<b>FBR Digital Fiscal Registration</b><br/>"
            f"<font size='7' color='#64748B'>"
            f"Document Type: {doc_title}<br/>"
            f"FBR Status: <b>{note.fbr_status}</b><br/>"
            f"FBR Ref: <b>{getattr(note, 'fbr_invoice_number', None) or getattr(note, 'fbr_reference', None) or 'Pending'}</b><br/>"
            f"Registered under Pakistan Sales Tax Act, 1990 & Digital Invoicing Rules."
            f"</font>"
        )

        qr_block = Table([[qr_drawing, Paragraph(fbr_note_text, self.styles["InvNormal"])]], colWidths=[28 * mm, 158 * mm])
        qr_block.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(KeepTogether(qr_block))

        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(
            "This is a system-generated electronic tax adjustment note created via FBR Invoice Cloud. "
            "Valid without physical signature under Pakistan Electronic Transactions Ordinance.",
            self.styles["InvSmall"]
        ))

        note_is_valid = (
            str(note.status).upper() in ("VALID", "ISSUED", "POSTED")
            and bool(getattr(note, "fbr_invoice_number", None) or getattr(note, "fbr_reference", None))
            and not bool(getattr(note, "fbr_is_simulated", False))
            and str(getattr(note, "fbr_environment", "DEMO")).upper() == "PRODUCTION"
            and str(getattr(note, "fbr_status", "")).upper() in ("VALID", "SUCCESS", "POSTED")
        )

        def _draw_note_watermark(canvas, document):
            if not note_is_valid:
                canvas.saveState()
                canvas.setFont("Helvetica-Bold", 34)
                canvas.setFillColor(colors.HexColor("#CBD5E1"), alpha=0.35)
                canvas.translate(A4[0] / 2, A4[1] / 2)
                canvas.rotate(45)
                canvas.drawCentredString(0, 0, "SIMULATED / PRE-SUBMISSION DRAFT")
                canvas.restoreState()

        doc.build(story, onFirstPage=_draw_note_watermark, onLaterPages=_draw_note_watermark)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

pdf_generator = PDFInvoiceGenerator()
