# User Acceptance Testing (UAT) Checklist

Use this checklist to verify the BIMCalc system in your staging environment before production deployment.

## 1. System Access & Security
- [x] **Login**: Access the application URL. Verify you are redirected to login (if auth is enabled) or dashboard.
- [x] **HTTPS**: Confirm the URL starts with `https://` and the browser shows a secure lock icon. (Verified locally via HTTP)
- [x] **Multi-Tenancy**:
    - [x] Create a new Organization/Project combo (e.g., `Org: TestCorp`, `Project: UAT-1`).
    - [x] Verify the dashboard is empty for this new project.

## 2. Data Ingestion
- [x] **Upload Schedule**:
    - [x] Go to **Ingest** page.
    - [x] Upload a sample Revit schedule (CSV or XLSX).
    - [x] **Verify**: Success message appears. Row count matches file.
- [x] **Upload Price Book**:
    - [x] Upload a sample Vendor Price Book.
    - [x] **Verify**: Success message appears.
- [ ] **Error Handling**:
    - [ ] Upload an invalid file (e.g., a text file renamed to .csv).
    - [ ] **Verify**: Error message is displayed. **Check Email/Slack for failure alert.**

## 3. Items & Prices
- [x] **Items List**:
    - [x] Go to **Items** page.
    - [x] Verify uploaded items are listed.
    - [x] Test **Search** (e.g., search for a specific family).
    - [x] Test **Filter** (e.g., by Category).
- [x] **Prices List**:
    - [x] Go to **Prices** page.
    - [x] Verify vendor prices are listed.
    - [x] Test **Search** by SKU or description.

## 4. Matching Pipeline
- [x] **Run Matching**:
    - [x] Go to **Match** page.
    - [x] Click **"Run Matching"** button.
    - [x] **Verify**: Progress indicator appears. Dashboard updates with match percentages.
- [x] **Review Dashboard**:
    - [x] Return to Dashboard.
    - [x] **Verify**: Match Percentage is non-zero. Health Score is calculated.

## 5. Review Workflow
- [ ] **Manual Review**:
    - [ ] Go to **Review** page.
    - [ ] Select an item.
    - [ ] **Approve**: Click "Approve" on a match candidate.
    - [ ] **Reject**: Click "Reject Match" on a candidate.
    - [ ] **Verify**: Item disappears from the list.
- [ ] **Verify Approval**:
    - [ ] Go to **Dashboard**. "Active Mappings" should increase by 1.

## 6. Reporting
- [ ] **Progress Dashboard**:
    - [ ] Go to **Progress** page.
    - [ ] Verify "Completion %" reflects your work.
- [ ] **Export Reports**:
    - [ ] Go to **Reports** (or Analytics).
    - [ ] Click **Export PDF**.
    - [ ] **Verify**: PDF downloads and contains correct data.
    - [ ] Click **Export Excel**.
    - [ ] **Verify**: Excel file downloads.

## 7. Operations (Optional)
- [ ] **Backup**: Run `./backup.sh` on the server. Verify a file is created in `backups/`.
- [ ] **Logs**: Check logs (`docker-compose logs -f web`) to ensure no errors during your test.

---

**Sign-off**:
- [ ] All Critical Workflows Passed
- [ ] No Blocking Bugs Found
- [ ] Ready for Production
