"""Quick test of classification system."""
from bimcalc.classification.trust_hierarchy import classify_item
from bimcalc.models import Item

# Test cable tray item (should be 66)
item1 = Item(
    org_id="test",
    project_id="test",
    family="Cable Tray - Ladder",
    type_name="Elbow 90deg 200x50mm",
    category="Cable Tray",
    width_mm=200.0,
    height_mm=50.0,
    angle_deg=90.0,
    material="galvanized_steel",
)

# Test LED panel (should be 95)
item2 = Item(
    org_id="test",
    project_id="test",
    family="LED Panel",
    type_name="600x600 40W",
    category="Lighting Fixtures",
    width_mm=600.0,
    height_mm=600.0,
)

#Test pipe (should be 2215)
item3 = Item(
    org_id="test",
    project_id="test",
    family="Pipe - Supply Water",
    type_name="90 Elbow DN50",
    category="Pipes",
    system_type="Domestic Cold Water",
    dn_mm=50.0,
    angle_deg=90.0,
    material="copper",
)

print("Testing classification:")
print(f"Cable Tray: {classify_item(item1)}")
print(f"LED Panel: {classify_item(item2)}")
print(f"Pipe: {classify_item(item3)}")
