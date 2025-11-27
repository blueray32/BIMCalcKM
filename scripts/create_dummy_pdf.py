from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def create_dummy_quote(filename):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Header
    elements.append(Paragraph("VENDOR QUOTE #Q-2023-001", styles['Heading1']))
    elements.append(Paragraph("Vendor: Acme Supplies Ltd.", styles['Normal']))
    elements.append(Paragraph("Date: 2023-10-27", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Data
    data = [
        ['Item Code', 'Description', 'Qty', 'Unit', 'Unit Price', 'Total'],
        ['ELEC-001', 'Copper Wire 2.5mm', '100', 'm', '1.50', '150.00'],
        ['ELEC-002', 'Socket Outlet Double', '50', 'ea', '4.25', '212.50'],
        ['HVAC-101', 'Ductwork Galvanized', '20', 'm2', '45.00', '900.00'],
        ['PLUM-555', 'Copper Pipe 15mm', '10', 'm', '8.00', '80.00'],
    ]

    # Table
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(t)

    doc.build(elements)
    print(f"Created {filename}")

if __name__ == "__main__":
    create_dummy_quote("dummy_quote.pdf")
