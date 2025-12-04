from fpdf import FPDF


def create_dummy_quote(filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="VENDOR QUOTE #Q-2023-001", ln=1, align="C")
    pdf.cell(200, 10, txt="Vendor: Acme Supplies Ltd.", ln=1, align="L")
    pdf.cell(200, 10, txt="Date: 2023-10-27", ln=1, align="L")
    pdf.ln(10)

    # Header
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 10, "Item Code", 1)
    pdf.cell(60, 10, "Description", 1)
    pdf.cell(20, 10, "Qty", 1)
    pdf.cell(20, 10, "Unit", 1)
    pdf.cell(25, 10, "Price", 1)
    pdf.cell(25, 10, "Total", 1)
    pdf.ln()

    # Data
    data = [
        ["ELEC-001", "Copper Wire 2.5mm", "100", "m", "1.50", "150.00"],
        ["ELEC-002", "Socket Outlet Double", "50", "ea", "4.25", "212.50"],
        ["HVAC-101", "Ductwork Galvanized", "20", "m2", "45.00", "900.00"],
        ["PLUM-555", "Copper Pipe 15mm", "10", "m", "8.00", "80.00"],
    ]

    pdf.set_font("Arial", size=10)
    for row in data:
        pdf.cell(40, 10, row[0], 1)
        pdf.cell(60, 10, row[1], 1)
        pdf.cell(20, 10, row[2], 1)
        pdf.cell(20, 10, row[3], 1)
        pdf.cell(25, 10, row[4], 1)
        pdf.cell(25, 10, row[5], 1)
        pdf.ln()

    pdf.output(filename)
    print(f"Created {filename}")


if __name__ == "__main__":
    try:
        create_dummy_quote("dummy_quote.pdf")
    except ImportError:
        print("FPDF not found")
