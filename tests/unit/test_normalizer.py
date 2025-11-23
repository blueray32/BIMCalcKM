from bimcalc.canonical.normalizer import normalize_name, parse_attributes


def test_normalize_unifies_separators_and_strips_noise():
    s = normalize_name("Tray Elbow 90° 200×50 (Galv) - ProjectX Rev_1")
    assert "90" in s and "200x50" in s.replace("×","x").replace("  ", " ")
    assert "project" not in s and "rev" not in s

def test_parse_attributes_extracts_dimensions_angle_material():
    attrs = parse_attributes("Tray Elbow 90° 200×50 galvanised")
    assert attrs["width_mm"] == 200
    assert attrs["height_mm"] == 50
    assert attrs["angle_deg"] == 90
    assert attrs["material"] == "galv"
