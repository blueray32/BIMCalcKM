import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not set")
    exit(1)

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def check_integrity():
    print("🔍 Starting Data Integrity Check...")

    async with async_session() as session:
        # 1. Check for orphaned match results
        print("\n1️⃣ Checking for orphaned match_results...")
        result = await session.execute(
            text("""
            SELECT COUNT(*) FROM match_results mr 
            WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.id = mr.item_id)
        """)
        )
        orphaned_matches = result.scalar()
        if orphaned_matches > 0:
            print(f"❌ Found {orphaned_matches} orphaned match_results!")
        else:
            print("✅ No orphaned match_results found.")

        # 2. Check for orphaned item mappings
        print("\n2️⃣ Checking for orphaned item_mappings...")
        result = await session.execute(
            text("""
            SELECT COUNT(*) FROM item_mapping im 
            WHERE NOT EXISTS (SELECT 1 FROM price_items pi WHERE pi.id = im.price_item_id)
        """)
        )
        orphaned_mappings = result.scalar()
        if orphaned_mappings > 0:
            print(f"❌ Found {orphaned_mappings} orphaned item_mappings!")
        else:
            print("✅ No orphaned item_mappings found.")

        # 3. Check SCD Type-2 Invariants (Price Items)
        print("\n3️⃣ Checking SCD Type-2 Invariants (Price Items)...")
        result = await session.execute(
            text("""
            SELECT org_id, item_code, region, COUNT(*) 
            FROM price_items 
            WHERE is_current = true 
            GROUP BY org_id, item_code, region 
            HAVING COUNT(*) > 1
        """)
        )
        duplicates = result.fetchall()
        if duplicates:
            print(f"❌ Found {len(duplicates)} keys with multiple current versions!")
            for row in duplicates:
                print(
                    f"   - Org: {row.org_id}, Code: {row.item_code}, Region: {row.region}"
                )
        else:
            print("✅ SCD Type-2 invariant holds (max 1 current version per key).")

        # 4. Check SCD Type-2 Invariants (Item Mappings)
        print("\n4️⃣ Checking SCD Type-2 Invariants (Item Mappings)...")
        result = await session.execute(
            text("""
            SELECT org_id, canonical_key, COUNT(*) 
            FROM item_mapping 
            WHERE end_ts IS NULL 
            GROUP BY org_id, canonical_key 
            HAVING COUNT(*) > 1
        """)
        )
        duplicates = result.fetchall()
        if duplicates:
            print(f"❌ Found {len(duplicates)} keys with multiple active mappings!")
            for row in duplicates:
                print(f"   - Org: {row.org_id}, Key: {row.canonical_key}")
        else:
            print("✅ SCD Type-2 invariant holds (max 1 active mapping per key).")

        # 5. Check Multi-Tenant Isolation (Sample)
        print("\n5️⃣ Checking Multi-Tenant Isolation (Sample)...")
        # Ensure items don't share IDs across orgs (UUIDs make this unlikely, but good to check logic)
        result = await session.execute(
            text("""
            SELECT id, COUNT(DISTINCT org_id) 
            FROM items 
            GROUP BY id 
            HAVING COUNT(DISTINCT org_id) > 1
        """)
        )
        leaks = result.fetchall()
        if leaks:
            print(f"❌ Found {len(leaks)} items shared across organizations!")
        else:
            print("✅ No cross-tenant item ID collisions.")

    print("\n🏁 Integrity Check Complete.")


if __name__ == "__main__":
    asyncio.run(check_integrity())
