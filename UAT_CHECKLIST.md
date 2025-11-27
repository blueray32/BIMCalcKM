# User Acceptance Testing (UAT) Checklist

Use this checklist to verify the BIMCalc system in your staging environment before production deployment.

## 1. System Access & Security
- [ ] **Login**: Access the application URL. Verify you are redirected to login (if auth is enabled) or dashboard.
- [ ] **HTTPS**: Confirm the URL starts with `https://` and the browser shows a secure lock icon.
- [ ] **Multi-Tenancy**:
    - [ ] Create a new Organization/Project combo (e.g., `Org: TestCorp`, `Project: UAT-1`).
    - [ ] Verify the dashboard is empty for this new project.

## 2. Data Ingestion
- [ ] **Upload Schedule**:
    - [ ] Go to **Ingest** page.
    - [ ] Upload a sample Revit schedule (CSV or XLSX).
    - [ ] **Verify**: Success message appears. Row count matches file.
- [ ] **Upload Price Book**:
    - [ ] Upload a sample Vendor Price Book.
    - [ ] **Verify**: Success message appears.
- [ ] **Error Handling**:
    - [ ] Upload an invalid file (e.g., a text file renamed to .csv).
    - [ ] **Verify**: Error message is displayed. **Check Email/Slack for failure alert.**

## 3. Items & Prices
- [ ] **Items List**:
    - [ ] Go to **Items** page.
    - [ ] Verify uploaded items are listed.
    - [ ] Test **Search** (e.g., search for a specific family).
    - [ ] Test **Filter** (e.g., by Category).
- [ ] **Prices List**:
    - [ ] Go to **Prices** page.
    - [ ] Verify vendor prices are listed.
    - [ ] Check that `Valid From` dates are correct.

## 4. Matching Pipeline
- [ ] **Run Match**:
    - [ ] Go to **Match** page.
    - [ ] Click **Run Matching**.
    - [ ] **Verify**: Progress bar updates. "Matching Complete" message appears.
- [ ] **Verify Results**:
    - [ ] Check the **Dashboard**. "Active Mappings" and "Awaiting Review" counts should update.

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
