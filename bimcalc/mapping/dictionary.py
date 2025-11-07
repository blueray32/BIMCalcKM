from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class MappingRow:
    canonical_key: str
    price_item_id: int

class InMemoryDictionary:
    """Demo dictionary; replace with DB-backed SCD2 in production."""
    def __init__(self) -> None:
        self._store: Dict[str, MappingRow] = {}

    def get(self, key: str) -> Optional[MappingRow]:
        return self._store.get(key)

    def put(self, key: str, price_item_id: int) -> None:
        self._store[key] = MappingRow(key, price_item_id)
