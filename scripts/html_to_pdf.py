import re
from fpdf import FPDF


def extract_text(html_content):
    # Remove scripts and styles
    html_content = re.sub(r"<script.*?</script>", "", html_content, flags=re.DOTALL)
    html_content = re.sub(r"<style.*?</style>", "", html_content, flags=re.DOTALL)
    # Replace breaks with newlines
    html_content = re.sub(r"<br\s*/?>", "\n", html_content)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", html_content)
    # Clean whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = "\n".join(chunk for chunk in chunks if chunk)
    return text


def create_pdf(text, filename="tlc_simulation.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # Add a title
    pdf.set_font("Arial", style="B", size=16)
    pdf.cell(200, 10, txt="TLC Direct Product Page Simulation", ln=1, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", size=10)
    # Write text line by line to avoid overflow issues (basic implementation)
    for line in text.split("\n"):
        try:
            # Replace common unicode chars that might break latin-1
            safe_line = line.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 5, txt=safe_line)
        except Exception:
            continue

    pdf.output(filename)


if __name__ == "__main__":
    with open("tlc_raw.html", "r") as f:
        html = f.read()

    text = extract_text(html)
    create_pdf(text)
    print("PDF created successfully")
