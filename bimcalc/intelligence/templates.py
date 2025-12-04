"""Pre-built checklist templates for common classifications."""

# Pre-built templates for common item types
BUILTIN_TEMPLATES = {
    "electrical_panel": {
        "name": "Electrical Panel QA Checklist",
        "description": "Standard QA checklist for electrical panels and distribution boards",
        "classification_codes": ["2601", "2602"],
        "category": "Electrical",
        "items": [
            {
                "id": 1,
                "requirement": "Visual inspection: No physical damage to panel or enclosure",
                "category": "Inspection",
                "priority": "High",
                "estimated_time_minutes": 5,
            },
            {
                "id": 2,
                "requirement": "Verify all cable glands and entries are properly sealed",
                "category": "Installation",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
            {
                "id": 3,
                "requirement": "Power supply test: Voltage within tolerance (±10%)",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 15,
            },
            {
                "id": 4,
                "requirement": "Circuit breaker operation test",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 20,
            },
            {
                "id": 5,
                "requirement": "Earth continuity test passed",
                "category": "Safety",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
            {
                "id": 6,
                "requirement": "Installation certificate completed and signed",
                "category": "Documentation",
                "priority": "Medium",
                "estimated_time_minutes": 5,
            },
        ],
    },
    "fire_alarm": {
        "name": "Fire Alarm System QA Checklist",
        "description": "Standard QA checklist for fire alarm control panels and detectors",
        "classification_codes": ["2801", "2802"],
        "category": "Fire Safety",
        "items": [
            {
                "id": 1,
                "requirement": "Visual inspection: Panel and devices undamaged",
                "category": "Inspection",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
            {
                "id": 2,
                "requirement": "All zones detected and identified correctly",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 15,
            },
            {
                "id": 3,
                "requirement": "Alarm activation test: All sounders operational",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 20,
            },
            {
                "id": 4,
                "requirement": "Battery backup test: Maintains operation for required duration",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 30,
            },
            {
                "id": 5,
                "requirement": "Detector sensitivity test passed",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 25,
            },
            {
                "id": 6,
                "requirement": "Fire brigade connection verified",
                "category": "Safety",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
            {
                "id": 7,
                "requirement": "BS 5839 compliance certificate issued",
                "category": "Documentation",
                "priority": "High",
                "estimated_time_minutes": 5,
            },
        ],
    },
    "hvac_unit": {
        "name": "HVAC Unit QA Checklist",
        "description": "Standard QA checklist for HVAC units and air handling equipment",
        "classification_codes": ["2701", "2702", "2703"],
        "category": "HVAC",
        "items": [
            {
                "id": 1,
                "requirement": "Visual inspection: Unit and connections intact",
                "category": "Inspection",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
            {
                "id": 2,
                "requirement": "Airflow test: CFM within design parameters",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 20,
            },
            {
                "id": 3,
                "requirement": "Temperature control test: Setpoints achieved",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 30,
            },
            {
                "id": 4,
                "requirement": "Filter installation verified and clean",
                "category": "Installation",
                "priority": "Medium",
                "estimated_time_minutes": 5,
            },
            {
                "id": 5,
                "requirement": "Noise level test: Within acceptable limits",
                "category": "Testing",
                "priority": "Medium",
                "estimated_time_minutes": 15,
            },
            {
                "id": 6,
                "requirement": "Vibration dampening properly installed",
                "category": "Installation",
                "priority": "Medium",
                "estimated_time_minutes": 10,
            },
            {
                "id": 7,
                "requirement": "Commissioning report completed",
                "category": "Documentation",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
        ],
    },
    "plumbing_fixture": {
        "name": "Plumbing Fixture QA Checklist",
        "description": "Standard QA checklist for plumbing fixtures and fittings",
        "classification_codes": ["3201", "3202"],
        "category": "Plumbing",
        "items": [
            {
                "id": 1,
                "requirement": "Visual inspection: No damage or defects",
                "category": "Inspection",
                "priority": "High",
                "estimated_time_minutes": 5,
            },
            {
                "id": 2,
                "requirement": "Leak test: All connections watertight",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 15,
            },
            {
                "id": 3,
                "requirement": "Flow rate test: Within specification",
                "category": "Testing",
                "priority": "Medium",
                "estimated_time_minutes": 10,
            },
            {
                "id": 4,
                "requirement": "Drainage test: Proper flow and no obstructions",
                "category": "Testing",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
            {
                "id": 5,
                "requirement": "Isolation valves operational",
                "category": "Testing",
                "priority": "Medium",
                "estimated_time_minutes": 5,
            },
            {
                "id": 6,
                "requirement": "Installation compliance with building codes",
                "category": "Documentation",
                "priority": "High",
                "estimated_time_minutes": 5,
            },
        ],
    },
    "cable_tray": {
        "name": "Cable Tray QA Checklist",
        "description": "Standard QA checklist for cable tray systems",
        "classification_codes": ["2620", "2621"],
        "category": "Electrical Distribution",
        "items": [
            {
                "id": 1,
                "requirement": "Visual inspection: Tray sections aligned and undamaged",
                "category": "Inspection",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
            {
                "id": 2,
                "requirement": "Support spacing within manufacturer specifications",
                "category": "Installation",
                "priority": "High",
                "estimated_time_minutes": 15,
            },
            {
                "id": 3,
                "requirement": "Earth bonding continuity verified",
                "category": "Safety",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
            {
                "id": 4,
                "requirement": "Cable fill capacity not exceeded",
                "category": "Installation",
                "priority": "Medium",
                "estimated_time_minutes": 15,
            },
            {
                "id": 5,
                "requirement": "Fire stopping at compartment boundaries installed",
                "category": "Safety",
                "priority": "High",
                "estimated_time_minutes": 10,
            },
            {
                "id": 6,
                "requirement": "As-built drawings updated",
                "category": "Documentation",
                "priority": "Medium",
                "estimated_time_minutes": 10,
            },
        ],
    },
}


async def seed_builtin_templates(session):
    """Seed database with built-in templates.

    Args:
        session: Database session
    """
    from bimcalc.db.models import ChecklistTemplateModel
    from sqlalchemy import select

    for template_key, template_data in BUILTIN_TEMPLATES.items():
        # Check if already exists
        query = select(ChecklistTemplateModel).where(
            ChecklistTemplateModel.name == template_data["name"],
            ChecklistTemplateModel.is_builtin == True,
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()

        if not existing:
            template = ChecklistTemplateModel(
                name=template_data["name"],
                description=template_data["description"],
                classification_codes=template_data["classification_codes"],
                category=template_data["category"],
                template_items={"items": template_data["items"]},
                is_builtin=True,
                created_by="system",
            )
            session.add(template)
            print(f"Added template: {template_data['name']}")

    await session.commit()
    print(f"Seeded {len(BUILTIN_TEMPLATES)} built-in templates")
