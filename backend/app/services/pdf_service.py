import io
import datetime
from decimal import Decimal
from typing import Optional, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget

from backend.app.models.invoice import Invoice


class PDFInvoiceGenerator:
    """Production ReportLab PDF generator for Pakistan FBR Tax Invoices.
    
    Adheres strictly to the FBR Digital Invoicing specifications, displaying:
    - Seller profile (Name, NTN, STRN, Branch, Province)
    - Buyer profile (Name, NTN/CNIC, STRN, Registration Type, Province, Address)
    - Fiscal metadata (Invoice #, Date, POS/FBR ID, QR Code)
    - Tabular line items with Pakistani tax breakdown (Gross, Disc, Taxable, Rate, Tax, Line Total)
    - Explicit DEMO/MOCK banner and watermark if simulated to prevent fraudulent compliance use.
    """

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

    def _build_qr_code(self, qr_text: str, size: float = 1.0 * inch) -> Drawing:
        """Create a vector QR Code drawing (PRAL v1.12 Section 4: 1.0 x 1.0 inch / 72 pt)."""
        qr = QrCodeWidget(qr_text)
        bounds = qr.getBounds()
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        drawing = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
        drawing.add(qr)
        return drawing

    def generate(self, invoice: Invoice, organization_name: Optional[str] = None) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=10 * mm,
            bottomMargin=12 * mm,
        )

        story = []

        # 0. Official PRAL / FBR Digital Invoicing System Badge (PRAL v1.12 Section 4)
        logo_badge_data = [[
            Paragraph("🏛️ <b>FEDERAL BOARD OF REVENUE</b> &nbsp;|&nbsp; DIGITAL INVOICING SYSTEM (PRAL)", self.styles["InvLogoBadge"]),
            Paragraph("<b>PRAL CERTIFIED E-INVOICE</b>", self.styles["InvLogoBadgeRight"])
        ]]
        logo_badge_table = Table(logo_badge_data, colWidths=[126 * mm, 60 * mm])
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

        # 1. Provenance / Simulation Banner if DEMO or MOCK
        is_demo = bool(invoice.fbr_is_simulated or invoice.fbr_environment == "DEMO" or invoice.fbr_provider == "MOCK")
        if is_demo:
            banner_data = [[
                Paragraph(
                    "⚠️ <b>DEMO MODE — NOT AN OFFICIAL FBR FISCAL DOCUMENT</b><br/>"
                    "Simulated compliance artifact for testing and development only. "
                    f"Provider: {invoice.fbr_provider or 'MOCK'} | Environment: {invoice.fbr_environment or 'DEMO'}",
                    self.styles["DemoBannerText"]
                )
            ]]
            banner_table = Table(banner_data, colWidths=[186 * mm])
            banner_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#F87171")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(banner_table)
            story.append(Spacer(1, 3 * mm))

        # 2. Header: Seller & Invoice Title
        seller_display_name = organization_name or invoice.seller_name or "Digital Taxpayer"
        seller_info = (
            f"<b>{seller_display_name}</b><br/>"
            f"NTN: <b>{invoice.seller_ntn or 'N/A'}</b> | STRN: <b>{invoice.seller_strn or 'N/A'}</b><br/>"
            f"Branch: {invoice.seller_branch_code or 'Head Office'} | Province: {invoice.seller_province or 'N/A'}"
        )

        inv_date_str = invoice.invoice_date.strftime("%d-%b-%Y") if invoice.invoice_date else "N/A"
        due_date_str = invoice.due_date.strftime("%d-%b-%Y") if invoice.due_date else "N/A"
        
        invoice_meta = (
            f"<b>SALES TAX INVOICE</b><br/>"
            f"Invoice No: <b>{invoice.invoice_number}</b><br/>"
            f"Date: <b>{inv_date_str}</b><br/>"
            f"Status: <b>{invoice.status}</b>"
        )

        header_table = Table(
            [
                [
                    Paragraph(seller_info, self.styles["InvNormal"]),
                    Paragraph(invoice_meta, self.styles["InvNormalBold"]),
                ]
            ],
            colWidths=[110 * mm, 76 * mm],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 2 * mm))
        story.append(HRFlowable(width="100%", thickness=1, color=self.border_color, spaceAfter=3 * mm))

        # 3. Buyer Block & Transaction Info
        buyer_reg_str = f"({invoice.buyer_registration_type})" if invoice.buyer_registration_type else ""
        buyer_col = (
            f"<b>BILL TO:</b><br/>"
            f"<b>{invoice.buyer_name}</b> {buyer_reg_str}<br/>"
            f"NTN: {invoice.buyer_ntn or 'N/A'} | STRN: {invoice.buyer_strn or 'N/A'}"
            f"{' | CNIC: ' + invoice.buyer_cnic if invoice.buyer_cnic else ''}<br/>"
            f"Province: {invoice.buyer_province or 'N/A'}<br/>"
            f"Address: {invoice.buyer_address or 'N/A'}"
        )

        fbr_ref = invoice.fbr_invoice_number or (f"SIM-{invoice.invoice_number}" if is_demo else "Pending Submission")
        sub_date_str = invoice.fbr_submission_date.strftime("%d-%b-%Y %H:%M UTC") if invoice.fbr_submission_date else "Not Submitted"

        fbr_meta_col = (
            f"<b>COMPLIANCE & FISCAL METRICS:</b><br/>"
            f"FBR Status: <b>{invoice.fbr_status}</b><br/>"
            f"FBR Inv No: <b>{fbr_ref}</b><br/>"
            f"Submission Date: {sub_date_str}<br/>"
            f"Payment Terms: {invoice.payment_terms or 'Immediate'}"
        )

        meta_table = Table(
            [
                [
                    Paragraph(buyer_col, self.styles["InvNormal"]),
                    Paragraph(fbr_meta_col, self.styles["InvNormal"]),
                ]
            ],
            colWidths=[105 * mm, 81 * mm],
        )
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

        # 4. Line Items Table
        items_header = [
            Paragraph("<b>#</b>", self.styles["InvTableHeader"]),
            Paragraph("<b>Description / HS Code</b>", self.styles["InvTableHeader"]),
            Paragraph("<b>Qty / UOM</b>", self.styles["InvTableHeader"]),
            Paragraph("<b>Unit Price</b>", self.styles["InvTableHeader"]),
            Paragraph("<b>Gross</b>", self.styles["InvTableHeader"]),
            Paragraph("<b>Disc</b>", self.styles["InvTableHeader"]),
            Paragraph("<b>Taxable</b>", self.styles["InvTableHeader"]),
            Paragraph("<b>Rate</b>", self.styles["InvTableHeader"]),
            Paragraph("<b>Tax Amt</b>", self.styles["InvTableHeader"]),
            Paragraph("<b>Total</b>", self.styles["InvTableHeader"]),
        ]

        table_rows = [items_header]

        for idx, item in enumerate(invoice.items, start=1):
            desc_text = f"<b>{item.item_code}</b> - {item.description}<br/><font color='#64748B'>HS: {item.hs_code}</font>"
            qty_text = f"{float(item.quantity):,.2f}<br/>{item.uom}"
            unit_price_text = f"{float(item.unit_price):,.2f}"
            gross_text = f"{float(item.gross_amount):,.2f}"
            disc_text = f"{float(item.discount):,.2f}"
            taxable_text = f"{float(item.taxable_amount):,.2f}"
            rate_text = f"{float(item.tax_rate):.1f}%"
            tax_amt_text = f"{float(item.tax_amount):,.2f}"
            line_total_text = f"{float(item.line_total):,.2f}"

            table_rows.append([
                Paragraph(str(idx), self.styles["InvTableCell"]),
                Paragraph(desc_text, self.styles["InvTableCell"]),
                Paragraph(qty_text, self.styles["InvTableCell"]),
                Paragraph(unit_price_text, self.styles["InvTableCellRight"]),
                Paragraph(gross_text, self.styles["InvTableCellRight"]),
                Paragraph(disc_text, self.styles["InvTableCellRight"]),
                Paragraph(taxable_text, self.styles["InvTableCellRight"]),
                Paragraph(rate_text, self.styles["InvTableCellRight"]),
                Paragraph(tax_amt_text, self.styles["InvTableCellRight"]),
                Paragraph(f"<b>{line_total_text}</b>", self.styles["InvTableCellRight"]),
            ])

        col_widths = [
            8 * mm,    # #
            56 * mm,   # Desc
            16 * mm,   # Qty/UOM
            18 * mm,   # Unit Price
            17 * mm,   # Gross
            13 * mm,   # Disc
            17 * mm,   # Taxable
            11 * mm,   # Rate
            14 * mm,   # Tax Amt
            16 * mm,   # Total
        ]

        items_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), self.primary_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.5, self.border_color),
        ]

        # Add alternating row colors for lines
        for r in range(1, len(table_rows)):
            if r % 2 == 0:
                table_style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F8FAFC")))

        items_table.setStyle(TableStyle(table_style))
        story.append(items_table)
        story.append(Spacer(1, 4 * mm))

        # 5. Summary & QR Code Block
        # Generate QR code representation
        qr_payload = invoice.fbr_qr_data
        if not qr_payload:
            # Standard simulated/preliminary QR payload
            qr_payload = (
                f"FBR-POS|INV:{invoice.fbr_invoice_number or invoice.invoice_number}|"
                f"NTN:{invoice.seller_ntn}|TOTAL:{invoice.grand_total}|TAX:{invoice.total_tax}"
            )
        qr_drawing = self._build_qr_code(qr_payload, size=1.0 * inch)

        summary_rows = [
            [Paragraph("Subtotal (Gross):", self.styles["InvTableCellBold"]), Paragraph(f"PKR {float(invoice.subtotal):,.2f}", self.styles["InvTableCellRight"])],
            [Paragraph("Total Discount:", self.styles["InvTableCellBold"]), Paragraph(f"PKR {float(invoice.total_discount):,.2f}", self.styles["InvTableCellRight"])],
            [Paragraph("Taxable Amount:", self.styles["InvTableCellBold"]), Paragraph(f"PKR {float(invoice.taxable_amount):,.2f}", self.styles["InvTableCellRight"])],
            [Paragraph("Total Sales Tax:", self.styles["InvTableCellBold"]), Paragraph(f"PKR {float(invoice.total_tax):,.2f}", self.styles["InvTableCellRight"])],
        ]
        if invoice.other_charges and float(invoice.other_charges) > 0:
            summary_rows.append([
                Paragraph("Other Charges:", self.styles["InvTableCellBold"]),
                Paragraph(f"PKR {float(invoice.other_charges):,.2f}", self.styles["InvTableCellRight"])
            ])
        summary_rows.append([
            Paragraph("<b>Grand Total:</b>", self.styles["InvSubtitle"]),
            Paragraph(f"<b>PKR {float(invoice.grand_total):,.2f}</b>", self.styles["InvSubtitle"])
        ])

        summary_table = Table(summary_rows, colWidths=[40 * mm, 45 * mm])
        summary_table.setStyle(TableStyle([
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("LINEABOVE", (0, -1), (-1, -1), 1, self.primary_color),
        ]))

        qr_text_note = (
            "<b>FBR Digital Verification</b><br/>"
            "<font size='6.5' color='#64748B'>"
            "Scan QR (1.0\" x 1.0\") to verify authenticity against FBR e-Invoicing portal.<br/>"
            f"FBR Ref: {invoice.fbr_invoice_number or 'Pending'}<br/>"
            "Issued in accordance with Sales Tax Rules, 2006."
            "</font>"
        )

        qr_block_data = [
            [
                qr_drawing,
                Paragraph(qr_text_note, self.styles["InvNormal"]),
                summary_table,
            ]
        ]
        qr_block_table = Table(qr_block_data, colWidths=[28 * mm, 73 * mm, 85 * mm])
        qr_block_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        story.append(KeepTogether(qr_block_table))

        # 6. Notes & Signatures
        if invoice.notes:
            story.append(Spacer(1, 3 * mm))
            notes_p = Paragraph(f"<b>Notes / Terms:</b> {invoice.notes}", self.styles["InvSmall"])
            story.append(notes_p)

        story.append(Spacer(1, 5 * mm))
        footer_p = Paragraph(
            "This is a system-generated electronic invoice created via FBR Invoice Cloud. "
            "Valid without physical signature under Pakistan Electronic Transactions Ordinance.",
            self.styles["InvSmall"]
        )
        story.append(footer_p)

        # Enforce watermark unless official valid production invoice
        is_valid_official = (
            str(invoice.status).upper() in ("VALID", "ISSUED", "PAID")
            and bool(invoice.fbr_invoice_number)
            and not bool(invoice.fbr_is_simulated)
            and str(invoice.fbr_environment).upper() == "PRODUCTION"
            and str(invoice.fbr_status).upper() in ("VALID", "SUCCESS", "POSTED")
        )

        def _draw_watermark(canvas, document):
            if not is_valid_official:
                canvas.saveState()
                canvas.setFont("Helvetica-Bold", 34)
                canvas.setFillColor(colors.HexColor("#CBD5E1"), alpha=0.35)
                canvas.translate(A4[0] / 2, A4[1] / 2)
                canvas.rotate(45)
                canvas.drawCentredString(0, 0, "SIMULATED / PRE-SUBMISSION DRAFT")
                canvas.restoreState()

        # Build document
        doc.build(story, onFirstPage=_draw_watermark, onLaterPages=_draw_watermark)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

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


# Global singleton
pdf_generator = PDFInvoiceGenerator()
