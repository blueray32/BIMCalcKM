# BIMCalc Intelligence Features - User Guide

**Version:** 1.0  
**Last Updated:** November 2025

---

## 🎯 Overview

BIMCalc's Intelligence features use AI to make your QA process faster, smarter, and more proactive. This guide shows you how to use each feature effectively.

---

## 📊 Analytics Dashboard

**What it does:** Provides visual insights into your project's health through 4 interactive charts.

**How to access:** Intelligence → Analytics

### The 4 Charts

#### 1. Classification Breakdown (Doughnut Chart)
Shows how many items you have in each classification category.

**Use it to:**
- Understand project composition
- Identify which trades dominate
- Plan resource allocation

#### 2. Compliance Trend (Line Chart)
Tracks QA completion percentage over time.

**Use it to:**
- Monitor QA progress
- Spot slowdowns early
- Report to stakeholders

#### 3. Cost Distribution (Bar Chart)
Shows total costs by classification.

**Use it to:**
- Identify expensive categories
- Budget planning
- Cost forecasting

#### 4. Document Coverage (Heatmap)
Matrix showing which document types exist for each classification.

**Use it to:**
- Find gaps in documentation
- Ensure compliance coverage
- Plan document collection

### Tips
- **Refresh data:** Click the ↻ button on any chart
- **Best viewed:** On larger screens for clarity
- **Update frequency:** Data cached for 10 minutes

---

## 🎯 Risk Dashboard

**What it does:** Identifies items likely to miss QA requirements before it becomes a problem.

**How to access:** Intelligence → Risk Dashboard

### Understanding Risk Scores

```
🟢 Low (0-30)     → On track, minimal attention needed
🟡 Medium (31-60) → Watch closely, may need support
🔴 High (61-100)  → Urgent attention required
```

### What Makes Items High-Risk?

Items get higher scores when they have:
- **No documents linked** (biggest factor)
- **Complex classification** (electrical, HVAC, etc.)
- **Old age** (>90 days without QA)
- **Low match confidence** (<70%)

### How to Use It

**1. Daily Check**
- Review the high-risk count in summary cards
- Focus on 🔴 High Risk items first

**2. Take Action**
- Click "Generate Checklist" for each high-risk item
- Link quality documents
- Assign for priority review

**3. Filter & Sort**
- Use dropdown to filter by risk level
- Highest scores = highest priority

### Best Practices
✅ Check daily for new high-risk items  
✅ Address items >80 score immediately  
✅ Link documents to reduce risk  
✅ Generate checklists for systematic QA

---

## 🧪 Auto-Generate QA Checklists

**What it does:** Creates comprehensive, item-specific testing checklists in ~10 seconds using AI.

**Traditional way:** 30+ minutes to create manually  
**AI way:** 90 seconds

### How to Generate a Checklist

**From Risk Dashboard:**
1. Go to Intelligence → Risk Dashboard
2. Find item needing checklist
3. Click "Generate Checklist" button
4. Wait ~10 seconds

**What Happens:**
1. AI finds relevant quality documents
2. Reads and analyzes requirements
3. Extracts testable items
4. Groups by category
5. Adds time estimates

### Understanding the Checklist

**Categories:**
- ✓ **Inspection** - Visual checks
- ✓ **Testing** - Functional tests
- ✓ **Safety** - Safety compliance
- ✓ **Installation** - Installation verification
- ✓ **Documentation** - Required paperwork

**Priority Levels:**
- **High** (!) - Must complete, critical
- **Medium** - Important but not urgent
- **Low** - Nice to have

**Time Estimates:**
Each item shows estimated minutes (e.g., 10 min, 20 min)

### Completing Checklists

**1. Check Off Items**
Click checkbox when complete → Progress bar updates automatically

**2. Track Progress**
Green progress bar shows % complete

**3. 100% Complete**
System marks with completion timestamp

### Best Practices
✅ Generate checklists **before** starting QA  
✅ Complete items in **priority order**  
✅ Don't skip high-priority items  
✅ Review auto-generated items for accuracy  
✅ Add notes for failed items

### Tips
- **Source documents shown:** See which standards were used
- **Regenerate if needed:** Delete and generate fresh
- **Edit after generation:** Checklists are editable
- **Share with team:** Export/print for collaboration

---

## 🤖 Smart Document Recommendations

**What it does:** AI suggests the most relevant quality documents for each item.

**How to access:** Review page → "🤖 Recommended" column

### How It Works

1. **AI analyzes** item details (family, type, classification)
2. **Searches** all quality documents
3. **Ranks** by relevance (0-100%)
4. **Shows** top 5 recommendations

### Understanding Recommendations

**Relevance Scores:**
- **80-100%** (Green) - Highly relevant, definitely use
- **60-79%** (Yellow) - Moderately relevant, review
- **<60%** (Gray) - Lower relevance, optional

### Best Practices
✅ Review **green** recommendations first  
✅ Link recommended docs to items  
✅ Use for research and context  
✅ Verify document applicability

---

## 🚀 Quick Start Guide

**Day 1: Get Familiar**
1. Visit Analytics Dashboard
2. Explore each chart
3. Understand project health

**Day 2: Identify Risks**
1. Open Risk Dashboard
2. Review high-risk items
3. Understand why they're high-risk

**Day 3: Generate Checklists**
1. Pick 2-3 high-risk items
2. Generate checklists
3. Review generated items

**Day 4: Complete QA**
1. Use checklists to guide testing
2. Check off completed items
3. Track progress

**Day 5: Optimize**
1. Link more documents
2. Reduce risk scores
3. Improve compliance %

---

## 💡 Pro Tips

### Maximize AI Accuracy
- **Upload quality documents** - More docs = better recommendations
- **Proper classification** - Helps AI understand context
- **Link documents** - Reduces risk scores

### Workflow Integration
1. **Morning:** Check Risk Dashboard
2. **During day:** Generate checklists as needed
3. **Evening:** Review Analytics for progress
4. **Weekly:** Check compliance trend

### Team Collaboration
- Share high-risk items in standups
- Assign checklist completion to specific people
- Use analytics in project reviews
- Export data for reports

---

## ❓ Common Questions

**Q: How does AI know which documents are relevant?**  
A: Uses vector similarity - analyzes text meaning, not just keywords.

**Q: Can I edit generated checklists?**  
A: Yes! Checklists are fully editable after generation.

**Q: How often does Risk Dashboard update?**  
A: Real-time. Scores update as you link docs or complete items.

**Q: What if AI generates wrong checklist items?**  
A: Review and edit. AI is very accurate but not perfect.

**Q: How much does AI cost?**  
A: ~$0.001 per checklist. Very affordable.

**Q: Can multiple people use checklists?**  
A: Currently single-user. Multi-user coming soon.

---

## 🆘 Getting Help

**Can't find something?**
- Check navigation: Intelligence dropdown
- Try the search feature
- Contact admin

**Feature not working?**
- Refresh the page
- Check if documents are uploaded
- Contact support

**Want training?**
- Video tutorials available
- Team training sessions offered
- Contact admin for scheduling

---

## 📈 Success Metrics

Track these to measure impact:

**Time Savings:**
- Before: 30+ min per checklist
- After: 90 seconds
- **Savings:** 95%+

**Risk Reduction:**
- Monitor high-risk count weekly
- Target: <10 high-risk items
- Goal: Early problem detection

**QA Quality:**
- Track compliance trend upward
- Reduce QA failures 50%+
- Better documentation coverage

---

**Need more help?** Contact your BIMCalc administrator or check the Admin Guide for technical details.
