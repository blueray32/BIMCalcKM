# Next Steps: Getting Started with BIMCalc

Now that BIMCalc is deployed and secured, here is how to start using it.

## 1. Import Price Data
Before matching items, you need a catalog of prices.

### Option A: Automated Sync (Crail4)
If you have configured the Crail4 integration, you can trigger a sync to fetch the latest market prices.
1.  SSH into the server:
    ```bash
    ssh -i deployment/deploy_key root@157.230.149.106
    ```
2.  Run the sync command:
    ```bash
    cd /opt/bimcalc
    docker compose exec app bimcalc sync-crail4 --org acme-construction
    ```

### Option B: Manual Import (CSV/Excel)
You can upload vendor price lists via the web interface.
1.  Log in to [https://bimcalc-staging.157.230.149.106.nip.io/](https://bimcalc-staging.157.230.149.106.nip.io/)
2.  Navigate to **/ingest** (or find "Ingest" in the menu).
3.  Upload your price book (CSV or Excel).
4.  Select the **Vendor** and click **Upload**.

## 2. Create a Project & Upload Schedule
Projects are created automatically when you upload a Revit schedule.

1.  Navigate to **/ingest**.
2.  Under "Upload Schedule", enter:
    *   **Organization ID**: e.g., `acme-construction`
    *   **Project ID**: e.g., `hospital-block-a` (This creates the project)
3.  Upload your Revit schedule export (CSV/Excel).
    *   *Required columns*: `Family`, `Type`
    *   *Optional*: `Category`, `System Type`, `Count`, `Width`, `Height`
4.  Click **Upload**.

## 3. Run Matching
Once you have prices and a schedule:

1.  Navigate to **/match**.
2.  Enter the **Organization ID** and **Project ID** you used above.
3.  Click **Run Matching**.
4.  The system will attempt to match your Revit items to the price catalog using:
    *   Exact classification codes
    *   Fuzzy text matching
    *   Historical learning

## 4. Review Results
1.  Navigate to **/review**.
2.  You will see items that need manual approval (low confidence matches).
3.  Approve or correct the matches. The system learns from your decisions!

## 5. View Analytics
1.  Navigate to the **Dashboard** (Home).
2.  View statistics on matched items, coverage, and potential savings.
