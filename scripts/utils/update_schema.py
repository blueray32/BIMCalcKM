import sqlite3
import os

DB_FILE = "bimcalc.db"

def update_schema():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        print("Adding labor_hours column...")
        cursor.execute("ALTER TABLE price_items ADD COLUMN labor_hours NUMERIC")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Skipping labor_hours: {e}")

    try:
        print("Adding labor_code column...")
        cursor.execute("ALTER TABLE price_items ADD COLUMN labor_code TEXT")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Skipping labor_code: {e}")

    try:
        print("Adding attributes column to items table...")
        # SQLite doesn't have a native JSON type, it uses TEXT
        cursor.execute("ALTER TABLE items ADD COLUMN attributes TEXT DEFAULT '{}'")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Skipping items.attributes: {e}")

    try:
        print("Creating document_links table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_links (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                url TEXT,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Skipping document_links: {e}")

    try:
        print("Adding source column to item_mapping table...")
        cursor.execute("ALTER TABLE item_mapping ADD COLUMN source TEXT")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Skipping item_mapping.source: {e}")

    try:
        print("Adding confidence_score column to item_mapping table...")
        cursor.execute("ALTER TABLE item_mapping ADD COLUMN confidence_score NUMERIC")
        print("Success.")
    except sqlite3.OperationalError as e:
        print(f"Skipping item_mapping.confidence_score: {e}")

    conn.commit()
    conn.close()
    print("Schema update complete.")

if __name__ == "__main__":
    update_schema()
