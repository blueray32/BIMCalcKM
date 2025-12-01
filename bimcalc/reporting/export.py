"""Export utilities for Scenario Planning."""

import pandas as pd
from io import BytesIO
from typing import List, Dict, Any
from datetime import datetime

def export_scenario_to_excel(
    scenario_data: Dict[str, Any],
    org_id: str,
    project_id: str
) -> BytesIO:
    """Generate an Excel file from scenario comparison data."""
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # 1. Summary Sheet
        summary_rows = []
        for vendor_data in scenario_data.get("comparisons", []):
            summary_rows.append({
                "Vendor": vendor_data["vendor_name"],
                "Total Cost": vendor_data["total_cost"],
                "Coverage %": vendor_data["coverage_percent"],
                "Matched Items": vendor_data["matched_items_count"],
                "Missing Items": vendor_data["missing_items_count"]
            })
            
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
        
        # 2. Detailed Sheets per Vendor
        for vendor_data in scenario_data.get("comparisons", []):
            vendor_name = vendor_data["vendor_name"][:30] # Excel sheet name limit
            details = vendor_data.get("details", [])
            if details:
                # Flatten details
                flat_details = []
                for d in details:
                    flat_details.append({
                        "Item Family": d.get("item_family"),
                        "Item Type": d.get("item_type"),
                        "Quantity": d.get("quantity"),
                        "Unit": d.get("unit"),
                        "Vendor Price": d.get("unit_price"),
                        "Line Total": d.get("line_total"),
                        "Status": d.get("status")
                    })
                pd.DataFrame(flat_details).to_excel(writer, sheet_name=vendor_name, index=False)
                
    output.seek(0)
    return output
