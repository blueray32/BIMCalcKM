"""Demo of enhanced confidence scoring with all strategies."""

from datetime import datetime
from uuid import uuid4

from bimcalc.canonical.enhanced_normalizer import get_normalizer
from bimcalc.matching.confidence import ConfidenceCalculator
from bimcalc.matching.matcher import MatchingPipeline
from bimcalc.matching.models import Item, MappingMemory, MappingRecord, PriceItem


def demo_exact_mpn_match() -> None:
    """Demonstrate exact MPN match → 100 confidence."""
    print("\n" + "=" * 70)
    print("DEMO 1: Exact MPN Match (→ 100 confidence)")
    print("=" * 70)

    item = Item(
        id=uuid4(),
        org_id="demo-org",
        project_id="proj-a",
        family="Pipe Elbow",
        type_name="90° DN100 Stainless Steel",
        manufacturer_part_number="ELB-90-100-SS",
    )

    price = PriceItem(
        id=uuid4(),
        classification_code=2215,
        sku="SKU-12345",
        manufacturer_part_number="ELB-90-100-SS",
        description="Elbow 90° DN100 SS Victaulic",
        unit_price=45.50,
    )

    calculator = ConfidenceCalculator()
    result = calculator.calculate(item, price)

    print(f"Item MPN: {item.manufacturer_part_number}")
    print(f"Price MPN: {price.manufacturer_part_number}")
    print(f"Confidence: {result.score}")
    print(f"Method: {result.method.value}")
    print(f"Details: {result.details}")


def demo_canonical_key_match() -> None:
    """Demonstrate canonical key mapping memory → 100 confidence."""
    print("\n" + "=" * 70)
    print("DEMO 2: Canonical Key Match (Previously Approved → 100 confidence)")
    print("=" * 70)

    # Project A: First approval
    item_project_a = Item(
        id=uuid4(),
        org_id="demo-org",
        project_id="project-a",
        canonical_key="2215/pipe_elbow/90_dn100_stainless_steel/ea",
        family="Pipe Elbow",
        type_name="90° DN100 SS",
        material="stainless_steel",
        unit="ea",
    )

    price = PriceItem(
        id=uuid4(),
        classification_code=2215,
        sku="ELB-90-100-SS",
        description="Elbow 90° DN100 Stainless",
        unit_price=45.50,
    )

    # Simulate manual approval and mapping memory write
    mapping_memory = MappingMemory()
    mapping = MappingRecord(
        id=uuid4(),
        org_id="demo-org",
        canonical_key="2215/pipe_elbow/90_dn100_stainless_steel/ea",
        price_item_id=price.id,
        start_ts=datetime.now(),
        created_by="engineer@example.com",
        reason="Manual approval in Project A",
    )
    mapping_memory.add(mapping)

    print("Project A: Manual approval saved to mapping memory")
    print(f"  Canonical Key: {item_project_a.canonical_key}")
    print(f"  Price Item: {price.sku}")

    # Project B: Same item, instant auto-match
    item_project_b = Item(
        id=uuid4(),
        org_id="demo-org",
        project_id="project-b",  # Different project!
        canonical_key="2215/pipe_elbow/90_dn100_stainless_steel/ea",  # Same key
        family="Pipe Elbow",
        type_name="90° DN100 Stainless Steel",
        material="stainless_steel",
        unit="ea",
    )

    calculator = ConfidenceCalculator()
    result = calculator.calculate(item_project_b, price, mapping_memory)

    print("\nProject B: Same item type")
    print(f"  Canonical Key: {item_project_b.canonical_key}")
    print(f"  Confidence: {result.score}")
    print(f"  Method: {result.method.value}")
    print("  → INSTANT AUTO-MATCH (no fuzzy search needed!)")


def demo_enhanced_fuzzy_perfect() -> None:
    """Demonstrate enhanced fuzzy with perfect match → ~95-100 confidence."""
    print("\n" + "=" * 70)
    print("DEMO 3: Enhanced Fuzzy - Perfect Match (→ 95-100 confidence)")
    print("=" * 70)

    item = Item(
        id=uuid4(),
        org_id="demo-org",
        project_id="proj-a",
        family="Duct Rectangular",
        type_name="400x200 Galvanized Steel",
        material="galvanized_steel",
        unit="m",
        width_mm=400.0,
        height_mm=200.0,
    )

    price = PriceItem(
        id=uuid4(),
        classification_code=2302,
        family="Duct Rectangular",
        type_name="400x200 Galvanized",
        material="galvanized_steel",
        unit="m",
        width_mm=400.0,
        height_mm=200.0,
        unit_price=35.20,
    )

    calculator = ConfidenceCalculator()
    result = calculator.calculate(item, price)

    print(f"Item: {item.family} {item.type_name}")
    print(f"Price: {price.family} {price.type_name}")
    print(f"Confidence: {result.score}")
    print(f"Method: {result.method.value}")
    print("\nField Scores:")
    for field, score in result.details["field_scores"].items():
        print(f"  {field}: {score}")
    print(f"Bonuses: {result.details['bonuses']}")


def demo_enhanced_fuzzy_with_flags() -> None:
    """Demonstrate enhanced fuzzy with mismatches → lower confidence + flags."""
    print("\n" + "=" * 70)
    print("DEMO 4: Enhanced Fuzzy - With Mismatches (→ lower confidence)")
    print("=" * 70)

    item = Item(
        id=uuid4(),
        org_id="demo-org",
        project_id="proj-a",
        family="Cable Tray Ladder",
        type_name="200x50 Stainless Steel",
        material="stainless_steel",
        unit="m",  # Note: unit is "m"
        width_mm=200.0,
        height_mm=50.0,
    )

    price = PriceItem(
        id=uuid4(),
        classification_code=2601,
        family="Cable Tray Ladder",
        type_name="200x50 Galvanized",  # Different material
        material="galvanized_steel",  # Mismatch!
        unit="ea",  # Different unit!
        width_mm=200.0,
        height_mm=50.0,
        unit_price=125.00,
    )

    calculator = ConfidenceCalculator()
    result = calculator.calculate(item, price)

    print(f"Item: {item.type_name} (unit: {item.unit}, material: {item.material})")
    print(f"Price: {price.type_name} (unit: {price.unit}, material: {price.material})")
    print(f"Confidence: {result.score}")
    print(f"Method: {result.method.value}")
    print("\nField Scores:")
    for field, score in result.details["field_scores"].items():
        print(f"  {field}: {score}")

    # Simulate flags
    flags = []
    if item.unit != price.unit:
        flags.append("UnitConflict")
    if item.material != price.material:
        flags.append("MaterialConflict")

    print(f"\nFlags Detected: {flags}")
    print("→ REQUIRES MANUAL REVIEW (Critical-Veto flags present)")


def demo_synonym_expansion() -> None:
    """Demonstrate synonym expansion improving match quality."""
    print("\n" + "=" * 70)
    print("DEMO 5: Synonym Expansion (SS → stainless_steel)")
    print("=" * 70)

    normalizer = get_normalizer()

    # Item uses "SS" abbreviation
    item_text = "Pipe Elbow 90° DN100 SS"
    item_normalized = normalizer.normalize(item_text, expand_synonyms=True)
    item_slug = normalizer.slug(item_text)

    # Price uses full name
    price_text = "Pipe Elbow 90° DN100 Stainless Steel"
    price_normalized = normalizer.normalize(price_text, expand_synonyms=True)
    price_slug = normalizer.slug(price_text)

    print(f"Item Original: {item_text}")
    print(f"Item Normalized: {item_normalized}")
    print(f"Item Slug: {item_slug}")
    print()
    print(f"Price Original: {price_text}")
    print(f"Price Normalized: {price_normalized}")
    print(f"Price Slug: {price_slug}")
    print()
    print("→ Both normalize to same form, improving fuzzy match score!")


def demo_complete_pipeline() -> None:
    """Demonstrate complete matching pipeline with classification blocking."""
    print("\n" + "=" * 70)
    print("DEMO 6: Complete Matching Pipeline")
    print("=" * 70)

    # Create item to match
    item = Item(
        id=uuid4(),
        org_id="demo-org",
        project_id="proj-a",
        classification_code=2215,  # Pipe fittings
        family="Pipe Elbow",
        type_name="90° DN100 Stainless Steel",
        material="stainless_steel",
        unit="ea",
        dn_mm=100.0,
        angle_deg=90.0,
    )

    # Create price catalog with multiple classifications
    price_catalog = [
        # Correct classification (2215 - pipe fittings)
        PriceItem(
            id=uuid4(),
            classification_code=2215,
            sku="ELB-90-100-SS",
            family="Pipe Elbow",
            type_name="90° DN100 Stainless",
            material="stainless_steel",
            unit="ea",
            dn_mm=100.0,
            angle_deg=90.0,
            unit_price=45.50,
        ),
        PriceItem(
            id=uuid4(),
            classification_code=2215,
            sku="ELB-90-100-CS",
            family="Pipe Elbow",
            type_name="90° DN100 Carbon Steel",
            material="carbon_steel",
            unit="ea",
            dn_mm=100.0,
            angle_deg=90.0,
            unit_price=32.00,
        ),
        # Wrong classification (2302 - ductwork) - should be filtered out
        PriceItem(
            id=uuid4(),
            classification_code=2302,
            sku="DUCT-ELB-400x200",
            family="Duct Elbow",
            type_name="90° 400x200",
            unit="ea",
            unit_price=125.00,
        ),
        # Wrong classification (2211 - piping) - should be filtered out
        PriceItem(
            id=uuid4(),
            classification_code=2211,
            sku="PIPE-DN100-SS",
            family="Pipe Straight",
            type_name="DN100 Stainless",
            unit="m",
            unit_price=28.50,
        ),
    ]

    pipeline = MatchingPipeline()
    result = pipeline.match_item(item, price_catalog)

    print(f"Item to match: {item.family} {item.type_name}")
    print(f"Item classification: {item.classification_code}")
    print(f"Total price catalog size: {len(price_catalog)} items")

    # Count candidates after blocking
    candidates = [
        p for p in price_catalog if p.classification_code == item.classification_code
    ]
    print(f"Candidates after classification blocking: {len(candidates)} items")
    print(f"→ Reduction: {len(price_catalog) - len(candidates)} items filtered out")

    if result:
        print("\nBest Match:")
        print(f"  Price SKU: {result.price_item_id}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Method: {result.method.value}")
        print(f"  Auto-Accepted: {result.auto_accepted}")
        print(f"  Flags: {result.flags if result.flags else 'None'}")
        print(f"  Reason: {result.reason}")


def main() -> None:
    """Run all demos."""
    print("\n")
    print("*" * 70)
    print("  BIMCalc Enhanced Confidence Scoring - Demo Suite")
    print("*" * 70)

    demo_exact_mpn_match()
    demo_canonical_key_match()
    demo_enhanced_fuzzy_perfect()
    demo_enhanced_fuzzy_with_flags()
    demo_synonym_expansion()
    demo_complete_pipeline()

    print("\n" + "=" * 70)
    print("All demos completed!")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
