from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Create a test invoice PDF
pdf_path = "staging_test_invoice.pdf"
c = canvas.Canvas(pdf_path, pagesize=letter)

# Title
c.setFont("Helvetica-Bold", 16)
c.drawString(100, 750, "Test Invoice - Phase 10 Verification")

# Table header
c.setFont("Helvetica-Bold", 12)
c.drawString(100, 700, "Item Description")
c.drawString(300, 700, "Qty")
c.drawString(350, 700, "Unit Price")
c.drawString(450, 700, "Total")

# Sample line items (pipe-delimited format for extraction)
c.setFont("Helvetica", 10)
items = [
    "Concrete Mix | 15 | 125.00 | 1875.00",
    "Steel Beams | 25 | 85.00 | 2125.00",
    "Electrical Wire | 100 | 12.50 | 1250.00",
    "Labor Hours | 40 | 65.00 | 2600.00",
]

y = 670
for item in items:
    c.drawString(100, y, item)
    y -= 25

# Total
c.setFont("Helvetica-Bold", 12)
c.drawString(350, y - 20, "Grand Total:")
c.drawString(450, y - 20, "$7,850.00")

c.save()
print(f"PDF created successfully: {pdf_path}")
