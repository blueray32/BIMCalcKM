# BIMCalc Project Intelligence User Guide

Welcome to BIMCalc's **Project Intelligence** features! This guide covers the new capabilities for document management, compliance tracking, and classification mapping.

---

## 1. Documents & Search

**Access:** Click "Documents" in the navigation bar

### Overview
Search and explore all project documents including contracts, manuals, specifications, and quality records.

![Documents Page](file:///Users/ciarancox/.gemini/antigravity/brain/ec805e23-f5f4-4b0b-85cc-c8be3aaada6e/documents_page_initial_1763924008539.png)

### Features

**Search Documents**
- Enter keywords in the search box (e.g., "warranty", "commissioning")
- Results update automatically based on document content

**Filter by Tags**
- Use the tag dropdown to filter by document type
- Common tags: `#Contract`, `#Manual`, `#Quality`, `#Electrical`

![Filtered Results](file:///Users/ciarancox/.gemini/antigravity/brain/ec805e23-f5f4-4b0b-85cc-c8be3aaada6e/documents_page_contract_1763924008928.png)

**Document Cards**
Each result shows:
- Document title
- Document type (PDF, DOCX, etc.)
- Relevant tags
- Source file path

---

## 2. Compliance Dashboard

**Access:** Click "Compliance" in the navigation bar

### Overview
Track quality assurance coverage across your project items. See which items have QA evidence (test packs, commissioning reports) and which are missing.

![Compliance Dashboard](file:///Users/ciarancox/.gemini/antigravity/brain/ec805e23-f5f4-4b0b-85cc-c8be3aaada6e/compliance_dashboard_1763924035489.png)

### Metrics

**Overview Cards**
- **Total Items**: All items ingested from schedules
- **Items with QA**: Items with linked quality documents
- **Completion %**: QA coverage percentage

**Coverage Chart**
- Visual breakdown by classification code
- Green bars: Items with QA evidence
- Red bars: Items missing QA

**Deficiency Table**
- Lists all items without QA documentation
- Sortable by classification, family, or type
- Use this to prioritize QA activities

### Use Cases
- **Project Managers**: Monitor overall QA progress
- **QA Teams**: Identify items needing inspection
- **Handover**: Verify all items have required documentation

---

## 3. Classification Management

**Access:** Click "Classifications" in the navigation bar

### Overview
Manage project-specific classification code mappings. Map your local codes (e.g., "61") to standard BIMCalc codes (e.g., "2601 - Electrical Distribution").

![Classifications Page](file:///Users/ciarancox/.gemini/antigravity/brain/ec805e23-f5f4-4b0b-85cc-c8be3aaada6e/classifications_page_1763924047704.png)

### Adding Mappings

1. Enter your **Local Code** (project-specific code from schedules)
2. Select **Standard Code** from dropdown
3. (Optional) Add description
4. Click "Add Mapping"

**Example:**
- Local Code: `61`
- Standard Code: `2601 - Electrical Power Distribution`
- Description: "Tritex project electrical code"

### Managing Mappings

**View:**
- All mappings displayed in table
- Shows local code, standard code, description, creator

**Delete:**
- Click "Delete" button next to mapping
- Confirm deletion

### When to Use
- **New Projects**: Define mappings before ingesting data
- **Legacy Systems**: Bridge old classification codes to BIMCalc
- **Multi-Standard Projects**: Handle multiple classification schemes

---

## 4. Review Queue Integration

**Access:** Navigate to "Review" page

### Overview
When items are flagged for review, the Review Queue now shows linked documents automatically.

### Documents Column
- New column in review table
- Shows count of linked documents for each item
- Click to view related contracts, specs, or QA records

### Benefits
- **Context**: See relevant docs while reviewing items
- **Efficiency**: No need to search separately
- **Accuracy**: Make informed decisions with all information

---

## Tips & Best Practices

### 📚 Documents
- Use specific keywords for better results
- Combine search and tag filtering for precision
- Review document tags to understand project structure

### ✅ Compliance
- Check dashboard weekly to track progress
- Export deficiency table for QA planning
- Use classification breakdown to spot problem areas

### 🏷️ Classifications
- Create mappings before ingesting schedules
- Document your naming conventions
- Review mappings if ingestion yields unexpected classifications

---

## Getting Started Checklist

- [ ] Navigate to each page to familiarize yourself
- [ ] Search for a document related to your current work
- [ ] Check compliance % for your project
- [ ] Add a test classification mapping
- [ ] Review items and observe linked documents

---

## Support

For technical issues or questions, contact your BIMCalc administrator or refer to the technical documentation.
