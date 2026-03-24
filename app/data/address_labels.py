"""
Local address label storage
Caches Arkham API results to minimize API calls
"""
import json
import asyncio
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime


class AddressLabelStorage:
    """Local storage for address labels"""
    
    def __init__(self, storage_path: str = "data/address_labels.json"):
        self.storage_path = Path(storage_path)
        self.labels: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
        self._load()
    
    def _load(self):
        """Load labels from disk"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.labels = json.load(f)
                print(f"📂 Loaded {len(self.labels)} address labels from cache")
            except Exception as e:
                print(f"⚠️  Failed to load address labels: {e}")
                self.labels = {}
        else:
            self.labels = {}
            # Create directory if needed
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def _save(self):
        """Save labels to disk"""
        async with self._lock:
            try:
                with open(self.storage_path, 'w', encoding='utf-8') as f:
                    json.dump(self.labels, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"⚠️  Failed to save address labels: {e}")
    
    async def get_label(self, address: str) -> Optional[Dict]:
        """Get label for address from cache"""
        address_lower = address.lower()
        return self.labels.get(address_lower)
    
    async def set_label(self, address: str, label_data: Dict):
        """Store label for address"""
        address_lower = address.lower()
        
        # Add metadata
        label_data["cached_at"] = datetime.utcnow().isoformat()
        label_data["original_address"] = address
        
        self.labels[address_lower] = label_data
        await self._save()
    
    async def get_missing_addresses(self, addresses: List[str]) -> List[str]:
        """Get list of addresses that don't have labels yet"""
        missing = []
        for address in addresses:
            if not await self.get_label(address):
                missing.append(address)
        return missing
    
    async def get_labels_batch(self, addresses: List[str]) -> Dict[str, Optional[Dict]]:
        """Get labels for multiple addresses from cache"""
        result = {}
        for address in addresses:
            result[address] = await self.get_label(address)
        return result
    
    async def set_labels_batch(self, labels: Dict[str, Dict]):
        """Store multiple labels at once"""
        for address, label_data in labels.items():
            if label_data:
                address_lower = address.lower()
                label_data["cached_at"] = datetime.utcnow().isoformat()
                label_data["original_address"] = address
                self.labels[address_lower] = label_data
        
        await self._save()
    
    def get_stats(self) -> Dict:
        """Get storage statistics"""
        labeled = sum(1 for label in self.labels.values() if label.get("label"))
        return {
            "total_addresses": len(self.labels),
            "labeled_addresses": labeled,
            "unlabeled_addresses": len(self.labels) - labeled
        }


# Global instance
address_storage = AddressLabelStorage()
