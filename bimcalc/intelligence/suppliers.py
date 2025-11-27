"""Supplier integration framework for fetching external pricing."""

import abc
import random
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class BaseSupplier(abc.ABC):
    """Abstract base class for supplier integrations."""
    
    @abc.abstractmethod
    async def search_item(self, query: str) -> List[Dict[str, Any]]:
        """Search for items in supplier catalog."""
        pass
    
    @abc.abstractmethod
    async def get_price(self, supplier_item_id: str) -> Optional[float]:
        """Get current price for a specific item."""
        pass

class DemoSupplier(BaseSupplier):
    """Demo supplier that simulates an external API."""
    
    def __init__(self, name: str = "Demo Supply Co."):
        self.name = name
        
    async def search_item(self, query: str) -> List[Dict[str, Any]]:
        """Simulate searching a catalog."""
        # In a real implementation, this would call an external API
        return [
            {
                "id": f"demo-{random.randint(1000, 9999)}",
                "name": f"{query} (Premium)",
                "price": random.uniform(50.0, 500.0),
                "currency": "EUR",
                "supplier": self.name
            }
        ]
    
    async def get_price(self, supplier_item_id: str) -> Optional[float]:
        """Simulate fetching a live price."""
        # Simulate network latency
        # await asyncio.sleep(0.5) 
        
        # Return a random price to simulate market fluctuations
        base_price = random.uniform(10.0, 1000.0)
        return round(base_price, 2)

class SupplierFactory:
    """Factory to get supplier instances."""
    
    @staticmethod
    def get_supplier(name: str = "demo") -> BaseSupplier:
        """Get a supplier instance by name."""
        if name.lower() == "demo":
            return DemoSupplier()
        # Add other suppliers here (e.g., Rexel, Wolseley)
        raise ValueError(f"Unknown supplier: {name}")

async def fetch_live_price_for_item(item_family: str, item_type: str) -> Dict[str, Any]:
    """Helper to fetch a live price for a BIM item."""
    supplier = SupplierFactory.get_supplier("demo")
    
    # In a real scenario, we might look up a mapped supplier ID first.
    # Here we just simulate a search and get a price.
    query = f"{item_family} {item_type}"
    
    # Simulate finding a match
    price = await supplier.get_price("simulated-id")
    
    return {
        "price": price,
        "currency": "EUR",
        "supplier": "Demo Supply Co.",
        "fetched_at": datetime.now().isoformat()
    }
