"""Generate large-scale test data for performance benchmarking.

Creates realistic price catalogs and item lists for testing BIMCalc performance
with 10K+ records.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bimcalc.db.models import Base, PriceItemModel

# Classification codes (from UniClass 2015)
CLASSIFICATIONS = {
    22: "Piping",
    66: "Cable Tray",
    67: "Cable Trunking",
    68: "Lighting",
    69: "Distribution Boards",
    70: "Switchgear",
}

# Product families by classification
PRODUCT_FAMILIES = {
    22: ["Pipe", "Elbow", "Tee", "Reducer", "Flange", "Valve"],
    66: ["Ladder", "Trough", "Cover", "Elbow", "Tee", "Reducer"],
    67: ["Trunking", "Coupler", "Elbow", "Tee", "End Cap"],
    68: ["LED Panel", "Downlight", "Floodlight", "Emergency Light", "Exit Sign"],
    69: ["Distribution Board", "Consumer Unit", "MCB", "RCD", "RCBO"],
    70: ["Switchgear", "Contactor", "Relay", "Timer", "Isolator"],
}

# Size ranges
WIDTHS = [50, 75, 100, 150, 200, 300, 400, 600]
HEIGHTS = [25, 50, 75, 100, 150]
DN_SIZES = [15, 20, 25, 32, 40, 50, 65, 80, 100, 150, 200]
ANGLES = [45, 90]

# Materials
MATERIALS = ["galvanized_steel", "stainless_steel", "aluminum", "pvc", "copper"]

# Vendors
VENDORS = ["vendor_a", "vendor_b", "vendor_c", "vendor_d", "vendor_e"]

# Regions
REGIONS = ["IE", "UK", "DE", "FR", "ES"]

# Organizations
ORGS = ["org_a", "org_b", "org_c"]


def generate_price_record(
    org_id: str,
    classification_code: int,
    index: int,
) -> PriceItemModel:
    """Generate a single realistic price record."""
    family_options = PRODUCT_FAMILIES[classification_code]
    family = random.choice(family_options)

    # Generate realistic attributes based on family
    width_mm = None
    height_mm = None
    dn_mm = None
    angle_deg = None
    material = random.choice(MATERIALS)

    if family in ["Ladder", "Trough", "Trunking"]:
        width_mm = float(random.choice(WIDTHS))
        height_mm = float(random.choice(HEIGHTS))
    elif family == "Pipe":
        dn_mm = float(random.choice(DN_SIZES))
    elif family in ["Elbow", "Tee"]:
        if classification_code in [66, 67]:  # Cable management
            width_mm = float(random.choice(WIDTHS))
            height_mm = float(random.choice(HEIGHTS))
            if family == "Elbow":
                angle_deg = float(random.choice(ANGLES))
        else:  # Piping
            dn_mm = float(random.choice(DN_SIZES))
            if family == "Elbow":
                angle_deg = float(random.choice(ANGLES))

    # Generate SKU and description
    vendor_id = random.choice(VENDORS)
    sku_parts = [
        CLASSIFICATIONS[classification_code][:3].upper(),
        family[:3].upper(),
        str(index).zfill(6),
    ]
    sku = "-".join(sku_parts)

    desc_parts = [CLASSIFICATIONS[classification_code], family]
    if width_mm:
        desc_parts.append(f"{int(width_mm)}mm width")
    if height_mm:
        desc_parts.append(f"{int(height_mm)}mm height")
    if dn_mm:
        desc_parts.append(f"DN{int(dn_mm)}")
    if angle_deg:
        desc_parts.append(f"{int(angle_deg)}°")
    if material:
        desc_parts.append(material.replace("_", " "))
    description = " ".join(desc_parts)

    # Generate realistic pricing
    base_price = 10.0
    if width_mm:
        base_price += width_mm * 0.1
    if height_mm:
        base_price += height_mm * 0.05
    if dn_mm:
        base_price += dn_mm * 0.5
    if material == "stainless_steel":
        base_price *= 2.0
    elif material == "copper":
        base_price *= 1.5

    # Add some randomness
    unit_price = Decimal(str(round(base_price * random.uniform(0.8, 1.2), 2)))

    region = random.choice(REGIONS)

    # Create unique item_code per (org, classification, family, index)
    item_code = (
        f"{org_id[:5].upper()}-{classification_code}-{family[:3].upper()}-{index:06d}"
    )

    return PriceItemModel(
        org_id=org_id,
        item_code=item_code,
        region=region,
        vendor_id=vendor_id,
        sku=sku,
        description=description,
        classification_code=classification_code,
        unit="m" if family in ["Ladder", "Trough", "Pipe", "Trunking"] else "ea",
        unit_price=unit_price,
        currency="EUR",
        source_name=f"{vendor_id}_catalog",
        source_currency="EUR",
        width_mm=width_mm,
        height_mm=height_mm,
        dn_mm=dn_mm,
        angle_deg=angle_deg,
        material=material,
        is_current=True,
        valid_from=datetime.utcnow() - timedelta(days=random.randint(30, 365)),
        last_updated=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
    )


async def generate_price_catalog(
    session: AsyncSession,
    org_id: str,
    num_prices: int = 10000,
    batch_size: int = 1000,
) -> None:
    """Generate and insert a large price catalog."""
    print(f"Generating {num_prices} price records for org '{org_id}'...")

    # Distribute across classifications
    prices_per_class = num_prices // len(CLASSIFICATIONS)

    total_inserted = 0
    for classification_code in CLASSIFICATIONS:
        print(
            f"  Generating {prices_per_class} prices for classification {classification_code}..."
        )

        for batch_start in range(0, prices_per_class, batch_size):
            batch_end = min(batch_start + batch_size, prices_per_class)
            batch = []

            for i in range(batch_start, batch_end):
                price_record = generate_price_record(org_id, classification_code, i)
                batch.append(price_record)

            session.add_all(batch)
            await session.flush()
            total_inserted += len(batch)

            if total_inserted % 1000 == 0:
                print(f"    Inserted {total_inserted} / {num_prices} prices...")

    await session.commit()
    print(f"✓ Successfully generated {total_inserted} price records")


async def main():
    """Generate test data for performance benchmarking."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate test data for performance testing"
    )
    parser.add_argument("--org", default="perf-test-org", help="Organization ID")
    parser.add_argument(
        "--num-prices", type=int, default=10000, help="Number of prices to generate"
    )
    parser.add_argument(
        "--database-url",
        default="sqlite+aiosqlite:///./bimcalc_perftest.db",
        help="Database URL",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("BIMCalc Performance Test Data Generator")
    print("=" * 60)
    print(f"Organization: {args.org}")
    print(f"Target prices: {args.num_prices}")
    print(f"Database: {args.database_url}")
    print("=" * 60)

    # Create engine and session
    engine = create_async_engine(args.database_url, echo=False)

    # Create tables
    print("\nCreating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Tables created")

    # Generate data
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        await generate_price_catalog(session, args.org, args.num_prices)

    # Report statistics
    print("\n" + "=" * 60)
    print("Data Generation Complete!")
    print("=" * 60)

    async with SessionLocal() as session:
        from sqlalchemy import func, select

        # Count by classification
        result = await session.execute(
            select(
                PriceItemModel.classification_code,
                func.count(PriceItemModel.id).label("count"),
            ).group_by(PriceItemModel.classification_code)
        )
        print("\nPrices by Classification:")
        for row in result:
            print(f"  Class {row.classification_code}: {row.count} prices")

        # Count by region
        result = await session.execute(
            select(
                PriceItemModel.region, func.count(PriceItemModel.id).label("count")
            ).group_by(PriceItemModel.region)
        )
        print("\nPrices by Region:")
        for row in result:
            print(f"  {row.region}: {row.count} prices")

    await engine.dispose()
    print("\n✓ Performance test database ready!")
    print(f"  Location: {args.database_url.replace('sqlite+aiosqlite:///', '')}")


if __name__ == "__main__":
    asyncio.run(main())
