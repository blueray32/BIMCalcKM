# Cost Estimation Progress Tracking - User Guide

## Overview

BIMCalc now includes a **Cost Estimation Workflow Progress Tracker** that provides real-time visibility into where your project stands in the cost estimation process. Unlike construction progress tracking (milestones like "Foundation Complete"), this feature tracks **your cost estimation workflow** progress.

## What It Tracks

The Progress tracker monitors four key workflow stages:

### 1. **Revit Schedule Import** (15% weight)
- Status: Completed when items are imported from Revit
- Shows: Total elements imported from Revit schedules

### 2. **Classification Assignment** (20% weight)
- Status: Tracks how many items have classification codes assigned
- Shows: % of items with OmniClass/UniClass codes
- Important: Classification is required for accurate matching

### 3. **Price Matching** (40% weight - MOST IMPORTANT)
- Status: Tracks how many items have been matched to price catalog items
- Shows: % of items with price matches
- Details:
  - High confidence (≥85%): Auto-approved
  - Medium confidence (70-84%): Requires review
  - Low confidence (<70%): Multiple candidates

### 4. **Manual Review & Approval** (25% weight)
- Status: Tracks review and approval progress
- Shows: Items pending review, critical flags
- Requires: Manual approval of flagged or low-confidence matches

## Accessing the Progress Dashboard

1. **Log in** to BIMCalc Management Console (default: http://localhost:8001)
2. Click the **"Progress"** tab in the top navigation (between Dashboard and Review)
3. Select your **organization** and **project** from the dropdown

## Dashboard Components

### Overall Completion Ring
- Large circular progress indicator showing overall project completion
- Color-coded:
  - **Green** (75-100%): Nearly complete
  - **Blue** (50-74%): Good progress
  - **Orange** (<50%): Early stages

### Workflow Stages
Four progress bars showing:
- **Status**: Completed ✓ | In Progress ⏳ | Not Started ☐
- **Completion %**: Visual bar and percentage
- **Item Count**: Completed / Total
- **Description**: Current state and details

### Statistics Cards
- **Total Items**: Elements imported from Revit
- **Matched Items**: Items with price matches
- **Pending Review**: Items awaiting manual approval
- **Critical Flags**: Items with blocking issues

### Charts
1. **Confidence Distribution** (Doughnut Chart)
   - Shows breakdown of match quality
   - Helps prioritize review efforts

2. **Classification Coverage** (Stacked Bar Chart)
   - Top 5 classification codes
   - Shows matched vs. unmatched items per code

### Next Steps Section
Smart action buttons based on your current progress:
- **Review N Items**: If items are pending review
- **Continue Matching**: If items remain unmatched
- **Resolve N Flags**: If critical flags exist
- **Generate Report**: Always available

## Typical Workflow

### Starting a New Project (0% Complete)
1. Import Revit schedules → **Import stage: 100%**
2. System auto-classifies items → **Classification stage: 80-100%**
3. Run matching pipeline → **Matching stage: 60-80%**
4. Review flagged items → **Review stage: 100%**
5. Generate cost report → **Overall: 100%**

### Monitoring Progress
- **Check Progress tab** regularly to see where you are
- **Yellow/orange bars** indicate areas needing attention
- **Critical flags** must be resolved before finalization

### Common Scenarios

#### Scenario: "68% Overall Complete"
- Import: ✓ Complete (100%)
- Classification: ✓ Complete (100%)
- Matching: ⏳ In Progress (68%)
- Review: ⏳ In Progress (40%)

**Action**: Click "Continue Matching" to match remaining items, then review pending items.

#### Scenario: "95% Complete but Can't Generate Report"
- Import: ✓ Complete (100%)
- Classification: ✓ Complete (100%)
- Matching: ✓ Complete (100%)
- Review: ⏳ In Progress (75%) - **50 items pending, 10 critical flags**

**Action**: Must resolve critical flags first. Click "Resolve 10 Flags" to fix blocking issues.

## Understanding Metrics

### Overall Completion Calculation
Weighted average of all stages:
```
Overall % = (Import × 0.15) + (Classification × 0.20) +
            (Matching × 0.40) + (Review × 0.25)
```

Matching has the **highest weight (40%)** because it's the core cost estimation task.

### Confidence Scores
- **High (85-100%)**: Auto-approved, no action needed
- **Medium (70-84%)**: Safe matches, but require manual review
- **Low (0-69%)**: Uncertain matches, user must choose from candidates

### Flags
- **Critical-Veto**: Block auto-approval (unit conflicts, size mismatches)
- **Advisory**: Warn but allow approval (stale prices, vendor notes)

## Integration with Other Features

### Progress → Review Workflow
- Progress shows **"50 items pending review"**
- Click **"Review 50 Items"** button
- Redirected to **Review page** with pending items

### Progress → Match Workflow
- Progress shows **"200 items unmatched"**
- Click **"Continue Matching"** button
- Redirected to **Match page** to run matching pipeline

### Progress → Reports
- When **100% complete**, click **"Generate Report"**
- Produces auditable cost report with all mappings

## API Integration

For programmatic access, the progress metrics are available via API:

```bash
# Get progress for a project
GET /progress?org=acme&project=building-a

# Returns JSON with all metrics (for automation/dashboards)
```

## Technical Details

### Data Sources
Progress is computed **on-the-fly** from existing data:
- **Items table**: Total items, classification coverage
- **Match results table**: Matched items, confidence scores
- **Flags table**: Critical and advisory flags
- **Mappings table**: Active SCD2 mappings

No new tables or data structures needed - all metrics derive from existing audit trail.

### Performance
- Progress calculation: ~100-200ms for typical projects (1,000-10,000 items)
- Cached: No (always real-time to show latest progress)
- Suitable for: On-demand dashboard viewing

### Refresh Rate
Progress updates **immediately** after:
- Running match pipeline
- Approving review items
- Importing new Revit schedules

## Troubleshooting

### Issue: "0% Complete - No items imported"
**Solution**: Go to **Ingest tab** → Upload Revit schedule CSV

### Issue: "Classification stage stuck at 50%"
**Solution**: Items missing classification codes. Check:
1. Revit families have OmniClass/UniClass parameters
2. System classification heuristics are enabled
3. Manual classification in Items page if needed

### Issue: "Matching stage stuck at 0%"
**Solution**: Go to **Match tab** → Click "Run Matching" to execute matching pipeline

### Issue: "Review stage shows 100 pending but I've approved them"
**Solution**: Refresh page - approved items should move to auto-approved count

### Issue: "Can't see Progress tab"
**Solution**: Ensure you're using `app_enhanced.py` (not the basic `app.py`). Check docker-compose.yml command.

## Best Practices

1. **Check Progress after each workflow step** to confirm completion
2. **Address critical flags immediately** - they block cost reporting
3. **Use classification coverage chart** to identify problematic categories
4. **Monitor confidence distribution** - aim for >80% high confidence
5. **Generate reports only at 100%** for complete cost data

## Related Documentation
- [BIMCalc README](README.md) - Overall system guide
- [Review UI Guide](ENHANCED_WEB_UI_GUIDE.md) - Manual review workflow
- [Classification Guide](docs/classification.md) - Classification codes
- [Matching Logic](docs/matching.md) - How matching works

---

**Questions or Issues?**
Report issues at: https://github.com/anthropics/bimcalc/issues (or your org's repo)

**Last Updated**: 2025-11-15
**Version**: 2.0 (with Cost Estimation Progress Tracking)
