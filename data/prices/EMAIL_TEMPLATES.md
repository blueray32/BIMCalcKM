# Email Templates for Requesting Price Lists

## Template 1: Initial Request (Professional)

```
Subject: Request for Product Catalog and Pricing Data

Dear [Account Manager Name],

I hope this email finds you well. We are implementing an automated cost
estimation system for our BIM projects and would like to integrate your
product pricing into our workflow.

Could you please provide us with a digital copy of your current price list
in one of the following formats:

**Preferred Format:** CSV or Excel

**Required Fields:**
- Product Code / SKU
- Product Description
- Unit Price
- Currency (EUR/GBP)
- Unit of Measure (ea, m, m², kg, etc.)

**Optional but Helpful:**
- Product Category / Classification
- Physical dimensions (width, height, diameter)
- Material type
- Lead time

**Frequency:**
Ideally, we would appreciate monthly or quarterly updates, though we're
happy to start with a one-time export to test the integration.

This will significantly improve our quoting accuracy and help us specify
your products more frequently in our projects.

Please let me know if you need any additional information or if there's
a standard format you already provide to other customers.

Thank you for your assistance.

Best regards,
[Your Name]
[Your Company]
[Phone]
[Email]
```

---

## Template 2: Follow-up Request (If No Response)

```
Subject: Following up: Price List Request

Hi [Name],

I'm following up on my email from [date] regarding obtaining your product
price list in digital format.

To clarify, we simply need:
✓ Product codes
✓ Descriptions
✓ Prices
✓ Units

Format: CSV, Excel, or even PDF (though structured data is preferred)

This is for our internal cost estimation system - we're not redistributing
your pricing data.

Could you let me know if this is something you can provide?

Thanks,
[Your Name]
```

---

## Template 3: Casual Request (For Established Relationships)

```
Subject: Quick Ask - Price List Export?

Hi [Name],

Quick question - any chance you could send me a CSV or Excel export of
your current price list?

We're setting up a new estimating system and want to make sure we're
using accurate pricing for your products.

Even just a one-time export would be helpful to get started.

Cheers,
[Your Name]
```

---

## Template 4: Request for Regular Updates

```
Subject: Automated Price List Updates - Request

Dear [Name],

Thank you for providing the initial price list. The integration is working
perfectly!

Would it be possible to receive regular updates? Ideally:

**Frequency:** Monthly (or quarterly if monthly isn't feasible)
**Delivery:** Email to [your-email@company.com]
**Format:** Same CSV/Excel format as before
**Subject Line:** "[Supplier Name] Price List - [Month Year]"

This would help us maintain accurate pricing and increase our usage of
your products in specifications.

If you have an automated export process, we're happy to work with whatever
format is easiest for you.

Thank you,
[Your Name]
```

---

## Template 5: Request for Specific Format (If They Ask)

```
Subject: Price List Format Specification

Hi [Name],

Thanks for agreeing to provide the price list! Here are the exact details
on what we need:

**File Format:**
- CSV (comma-separated values) or Excel (.xlsx)
- UTF-8 encoding preferred
- One header row with column names

**Required Columns:**
1. Product Code / SKU (unique identifier)
2. Description (product name/description)
3. Unit Price (numeric, ex-VAT preferred)
4. Currency (EUR, GBP, etc.)
5. Unit of Measure (ea, m, m², box, etc.)

**Optional Columns (very helpful if available):**
6. Product Category / Group
7. Width (mm)
8. Height (mm)
9. Diameter (mm)
10. Material Type
11. Manufacturer

**Example CSV:**
```csv
Product Code,Description,Unit Price,Currency,Unit,Category,Width,Height,Material
CT-200x50-90,Cable Tray Elbow 90° 200x50mm,45.50,EUR,ea,Cable Management,200,50,Galvanized Steel
CT-300x50-90,Cable Tray Elbow 90° 300x50mm,52.30,EUR,ea,Cable Management,300,50,Galvanized Steel
```

**Delivery:**
Email to: [your-email@company.com]
Or upload to: [shared drive/FTP if you have one]

Let me know if you have any questions!

Best regards,
[Your Name]
```

---

## Template 6: For Suppliers Who Only Offer PDF

```
Subject: Re: Price List - PDF to Structured Data?

Hi [Name],

Thank you for the PDF price list.

While we appreciate it, our system works best with structured data (CSV/Excel).
Is there any chance the source data behind the PDF is available in one of
these formats?

The PDF requires manual data entry on our end, which introduces errors and
takes significant time.

If CSV/Excel isn't possible, could you provide:
- An editable PDF (so we can copy/paste), or
- Access to your web-based catalog (if it has an export function)

Thanks for your understanding!

[Your Name]
```

---

## What to Do After You Receive the File

### 1. Check the File
```bash
# View first few rows
head -20 supplier_pricelist.csv

# Check encoding
file -I supplier_pricelist.csv

# Count rows
wc -l supplier_pricelist.csv
```

### 2. Place in Correct Location
```bash
# Copy to active directory
cp ~/Downloads/supplier_pricelist.csv /Users/ciarancox/BIMCalcKM/data/prices/active/

# Rename with date
mv supplier_pricelist.csv rexel_ie_20251114.csv
```

### 3. Configure Pipeline
Edit `config/pipeline_sources.yaml` to add your new source.

See `README.md` in this directory for configuration examples.

---

## Tips for Success

### ✅ Do:
- Be professional and explain the business value
- Make it easy for them (offer to work with any format)
- Follow up politely if no response in 1 week
- Thank them when they provide data
- Keep them updated on how it's working

### ❌ Don't:
- Don't share their pricing with competitors
- Don't be pushy about format requirements
- Don't expect real-time API access immediately
- Don't forget to archive old price lists

---

## Common Responses & How to Handle

### "We don't provide digital price lists"
→ Ask if they can export from their own system for internal use
→ Offer to accept any format and you'll convert it
→ Suggest you could manually enter from their website/catalog

### "That's confidential information"
→ Reassure you're a customer, not competitor
→ Explain it's for internal estimating only
→ Offer to sign NDA if needed
→ Show you're already buying from them

### "We only have PDF catalogs"
→ Ask if the PDF is text-searchable
→ Request the source file used to create the PDF
→ Offer to use their online catalog instead

### "This will take time to set up"
→ Start with one-time export to prove value
→ Offer to wait for next scheduled catalog update
→ Suggest quarterly updates instead of monthly

### "Our IT won't allow email attachments that large"
→ Suggest Dropbox/Google Drive/OneDrive link
→ Offer to provide FTP credentials
→ Ask about splitting into multiple smaller files

---

## Success Metrics

**After 1 Month:**
- [ ] 2-3 suppliers providing CSV price lists
- [ ] At least 500+ products imported
- [ ] Price lists updating monthly or quarterly

**After 3 Months:**
- [ ] 5+ suppliers integrated
- [ ] 2000+ products in database
- [ ] Automated email ingestion working
- [ ] 80%+ of project items matching to prices

---

Good luck! Most suppliers are happy to help once they understand it
benefits both parties.
