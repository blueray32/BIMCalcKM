import sys
import pandas as pd
import os
import asyncio
from decimal import Decimal
from uuid import uuid4
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.db.connection import get_session
from bimcalc.db.models import ItemModel

async def ingest_schedule(file_path, org_id="default", project_id="tritex24-229"):
    print(f"Ingesting: {file_path}")
    
    try:
        # Skip first row (metadata) and use second row as header if needed, 
        # but based on analysis, headers are on row 2 (index 1) or 3 (index 2)
        # Let's try to find the header row containing "Cable ID" or "Reference"
        df_preview = pd.read_excel(file_path, nrows=10, header=None)
        header_row = None
        for i, row in df_preview.iterrows():
            row_values = [str(v).lower() for v in row.values]
            if "cable id" in row_values: # Strict check for Cable ID
                header_row = i
                break
        
        if header_row is None:
            # Fallback for other formats
            for i, row in df_preview.iterrows():
                 row_values = [str(v).lower() for v in row.values]
                 if "reference" in row_values and "description" in row_values:
                     header_row = i
                     break
        
        if header_row is None:
            print("Could not find header row. Skipping.")
            return

        df = pd.read_excel(file_path, header=header_row)
        
        items = []
        for _, row in df.iterrows():
            # Basic validation - skip empty rows
            if pd.isna(row.get('Cable ID')) and pd.isna(row.get('Reference')):
                continue

            # Extract attributes
            attrs = {}
            for col in df.columns:
                val = row[col]
                if pd.notna(val):
                    attrs[str(col)] = val

            # Create ItemModel
            item = ItemModel(
                id=uuid4(),
                org_id=org_id,
                project_id=project_id,
                family="Electrical Distribution", # Generic family for now
                type_name=str(row.get('Reference') or row.get('Cable ID') or "Unknown Type"),
                classification_code=61, # Project specific code
                attributes=attrs,
                source_file=os.path.basename(file_path),
                created_at=datetime.utcnow()
            )
            items.append(item)

        print(f"Found {len(items)} items.")
        
        # Save to DB
        async with get_session() as session:
            for item in items:
                session.add(item)
            await session.commit()
            print("Saved to database.")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_tritex_schedules.py <file_path_or_directory> ...")
        sys.exit(1)

    files_to_process = []
    for path in sys.argv[1:]:
        if os.path.isdir(path):
            print(f"Scanning directory: {path}")
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".xlsx") and ("Schedule" in file or "DB" in file) and not file.startswith("~$"):
                        files_to_process.append(os.path.join(root, file))
        else:
            files_to_process.append(path)

    print(f"Found {len(files_to_process)} files to process.")
    for file_path in files_to_process:
        await ingest_schedule(file_path)

if __name__ == "__main__":
    asyncio.run(main())
