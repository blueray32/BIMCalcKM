from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)
pdf.cell(200, 10, txt="Invoice #12345", ln=1, align="C")
pdf.cell(200, 10, txt="Date: 2023-10-27", ln=1, align="L")
pdf.ln(10)

# Table Header
pdf.set_font("Arial", 'B', 12)
pdf.cell(80, 10, "Description", 1)
pdf.cell(30, 10, "Quantity", 1)
pdf.cell(30, 10, "Unit Price", 1)
pdf.cell(30, 10, "Total", 1)
pdf.ln()

# Table Rows
pdf.set_font("Arial", size=12)
data = [
    ("Concrete Mix", "10", "150.00", "1500.00"),
    ("Steel Rebar", "50", "20.00", "1000.00"),
    ("Labor Hours", "8", "50.00", "400.00"),
]

for row in data:
    pdf.cell(80, 10, row[0], 1)
    pdf.cell(30, 10, row[1], 1)
    pdf.cell(30, 10, row[2], 1)
    pdf.cell(30, 10, row[3], 1)
    pdf.ln()

pdf.output("test_invoice.pdf")
print("PDF created successfully")
