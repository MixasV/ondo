"""
Arkham Intelligence API Client
Provides address labeling and entity attribution
"""
import httpx
import asyncio
from typing import List, Dict, Optional
from app.config import settings
from app.data.address_labels import address_storage


class ArkhamClient:
    """Client for Arkham Intelligence API"""
    
    BASE_URL = "https://api.arkm.com"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.arkham_api_key
        self.headers = {"API-Key": self.api_key}
    
    async def get_address_label(self, address: str, use_cache: bool = True) -> Optional[Dict]:
        """Get label for a single address
        
        Args:
            address: Ethereum address to lookup
            use_cache: If True, check local cache first
        """
        # Check cache first
        if use_cache:
            cached = await address_storage.get_label(address)
            if cached:
                return cached
        
        # Fetch from API
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/intelligence/address/{address}",
                    headers=self.headers,
                    params={"chain": "ethereum"}
                )
                
                if response.status_code == 404:
                    # Store as "no label found"
                    await address_storage.set_label(address, {
                        "address": address,
                        "label": None,
                        "entity_type": None,
                        "chain": "ethereum"
                    })
                    return None
                
                if response.status_code == 429:
                    print(f"  ⚠️  Rate limited for {address[:10]}...")
                    return None
                
                if response.status_code == 502:
                    print(f"  ⚠️  Arkham API unavailable (502) for {address[:10]}...")
                    return None
                
                response.raise_for_status()
                data = response.json()
                
                # Extract label info
                label_data = {
                    "address": address,
                    "label": data.get("arkhamEntity", {}).get("name") or data.get("arkhamLabel", {}).get("name"),
                    "entity_type": data.get("arkhamEntity", {}).get("type"),
                    "chain": data.get("chain", "ethereum")
                }
                
                # Store in cache
                await address_storage.set_label(address, label_data)
                
                return label_data if label_data.get("label") else None
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                await address_storage.set_label(address, {
                    "address": address,
                    "label": None,
                    "entity_type": None,
                    "chain": "ethereum"
                })
                return None
            if e.response.status_code in [502, 503, 504]:
                # Server errors - don't cache, just skip
                return None
            print(f"  ⚠️  Arkham API error for {address[:10]}...: {e}")
            return None
        except (asyncio.CancelledError, asyncio.TimeoutError):
            # Network issues - don't cache, just skip
            return None
        except Exception as e:
            print(f"  ⚠️  Arkham lookup failed for {address[:10]}...: {e}")
            return None
    
    async def get_labels_for_addresses(self, addresses: List[str]) -> Dict[str, Optional[Dict]]:
        """Get labels for multiple addresses (checks cache first, then fetches missing)
        
        Args:
            addresses: List of Ethereum addresses
            
        Returns:
            Dict mapping address to label data
        """
        if not addresses:
            return {}
        
        # Get cached labels
        cached_labels = await address_storage.get_labels_batch(addresses)
        
        # Find addresses that need API lookup
        missing = [addr for addr, label in cached_labels.items() if label is None]
        
        if missing:
            print(f"🏷️  Fetching labels for {len(missing)} new addresses from Arkham API...")
            
            # Fetch missing labels one by one (with rate limiting)
            for i, address in enumerate(missing):
                label_data = await self.get_address_label(address, use_cache=False)
                cached_labels[address] = label_data
                
                # Rate limiting: wait between requests
                if i < len(missing) - 1:
                    await asyncio.sleep(0.5)  # 500ms between requests
        
        return cached_labels
    
    async def enrich_whale_holders(self, whale_holders: List[Dict]) -> List[Dict]:
        """Enrich whale holder data with Arkham labels
        
        Args:
            whale_holders: List of whale holder dicts with 'holder' address field
            
        Returns:
            Enriched list with 'label' and 'entity_type' fields added
        """
        if not whale_holders:
            return []
        
        # Extract unique addresses
        addresses = list(set(whale.get("holder") for whale in whale_holders if whale.get("holder")))
        
        if not addresses:
            return whale_holders
        
        # Get stats
        stats = address_storage.get_stats()
        print(f"📊 Address cache: {stats['labeled_addresses']}/{stats['total_addresses']} labeled")
        
        # Get labels (from cache or API)
        labels = await self.get_labels_for_addresses(addresses)
        
        # Enrich whale data
        enriched = []
        for whale in whale_holders:
            address = whale.get("holder")
            label_data = labels.get(address)
            
            enriched_whale = whale.copy()
            if label_data and label_data.get("label"):
                enriched_whale["label"] = label_data["label"]
                enriched_whale["entity_type"] = label_data.get("entity_type")
            else:
                enriched_whale["label"] = None
                enriched_whale["entity_type"] = None
            
            enriched.append(enriched_whale)
        
        labeled_count = sum(1 for w in enriched if w.get("label"))
        print(f"✓ Enriched {labeled_count}/{len(addresses)} addresses with labels")
        
        return enriched
    
    async def get_transfers(
        self,
        token_address: str,
        start_timestamp: int = None,
        end_timestamp: int = None,
        min_amount: float = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get transfers for a token
        
        Args:
            token_address: Token contract address
            start_timestamp: Unix timestamp for start date
            end_timestamp: Unix timestamp for end date
            min_amount: Minimum transfer amount in tokens
            limit: Max number of results
            
        Returns:
            List of transfer dicts with from/to addresses and amounts
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                params = {
                    "chain": "ethereum",
                    "base": token_address,
                    "limit": limit
                }
                
                if start_timestamp:
                    params["timestampGte"] = start_timestamp
                if end_timestamp:
                    params["timestampLte"] = end_timestamp
                
                response = await client.get(
                    f"{self.BASE_URL}/transfers",
                    headers=self.headers,
                    params=params
                )
                
                if response.status_code == 429:
                    print(f"  ⚠️  Rate limited by Arkham API")
                    return []
                
                response.raise_for_status()
                data = response.json()
                
                transfers = data.get("transfers", [])
                
                # Filter by amount if specified
                if min_amount:
                    transfers = [t for t in transfers if float(t.get("unitValue", 0)) >= min_amount]
                
                return transfers
                
        except Exception as e:
            print(f"  ⚠️  Arkham transfers lookup failed: {e}")
            return []


# Global instance
arkham_client = ArkhamClient()
