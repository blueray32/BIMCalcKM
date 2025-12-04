def create_minimal_pdf(filename):
    # A minimal valid PDF with "Hello World" text
    # This is a raw PDF structure
    content = (
        b"%PDF-1.1\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog\n"
        b"/Pages 2 0 R\n"
        b">>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Type /Pages\n"
        b"/Kids [3 0 R]\n"
        b"/Count 1\n"
        b"/MediaBox [0 0 595 842]\n"
        b">>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<< /Type /Page\n"
        b"/Parent 2 0 R\n"
        b"/Resources << /Font << /F1 4 0 R >> >>\n"
        b"/Contents 5 0 R\n"
        b">>\n"
        b"endobj\n"
        b"4 0 obj\n"
        b"<< /Type /Font\n"
        b"/Subtype /Type1\n"
        b"/Name /F1\n"
        b"/BaseFont /Helvetica\n"
        b">>\n"
        b"endobj\n"
        b"5 0 obj\n"
        b"<< /Length 222 >>\n"
        b"stream\n"
        b"BT\n"
        b"/F1 12 Tf\n"
        b"70 700 Td\n"
        b"(VENDOR QUOTE #Q-2023-001) Tj\n"
        b"0 -20 Td\n"
        b"(Item: ELEC-001 Copper Wire 100m 150.00 EUR) Tj\n"
        b"0 -20 Td\n"
        b"(Item: ELEC-002 Socket Outlet 50ea 212.50 EUR) Tj\n"
        b"ET\n"
        b"endstream\n"
        b"endobj\n"
        b"xref\n"
        b"0 6\n"
        b"0000000000 65535 f \n"
        b"0000000010 00000 n \n"
        b"0000000060 00000 n \n"
        b"0000000157 00000 n \n"
        b"0000000306 00000 n \n"
        b"0000000403 00000 n \n"
        b"trailer\n"
        b"<< /Size 6\n"
        b"/Root 1 0 R\n"
        b">>\n"
        b"startxref\n"
        b"676\n"
        b"%%EOF\n"
    )

    with open(filename, "wb") as f:
        f.write(content)
    print(f"Created {filename}")


if __name__ == "__main__":
    create_minimal_pdf("dummy_quote.pdf")
