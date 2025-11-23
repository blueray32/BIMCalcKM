from bimcalc.canonical.normalizer import canonicalize
from bimcalc.mapping.dictionary import InMemoryDictionary


def test_two_pass_auto_match_demo():
    dict_ = InMemoryDictionary()
    key1 = canonicalize("Tray Elbow 90° 200×50 (Galv) - ProjectA")
    dict_.put(key1, price_item_id=101)
    key2 = canonicalize("Ladder Tray Bend 90 deg 200x50 GALV - ProjectB v2")
    # Should canonicalize to same key parts (angle, width, height, material)
    assert key1 == key2
    hit = dict_.get(key2)
    assert hit and hit.price_item_id == 101
