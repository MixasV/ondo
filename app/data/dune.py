import httpx
import asyncio
from typing import Optional
from app.config import settings


class DuneClient:
    """Client for Dune Analytics API"""
    
    BASE_URL = "https://api.dune.com/api/v1"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.dune_api_key
        self.headers = {"X-Dune-API-Key": self.api_key}
    
    async def execute_query(self, query_id: int, params: dict = None) -> dict:
        """Execute a Dune query and return results"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Execute query
            response = await client.post(
                f"{self.BASE_URL}/query/{query_id}/execute",
                headers=self.headers,
                json={"query_parameters": params or {}}
            )
            response.raise_for_status()
            execution = response.json()
            execution_id = execution["execution_id"]
            
            # Poll for results with retry logic
            max_attempts = 60  # 60 seconds max
            for attempt in range(max_attempts):
                try:
                    status_response = await client.get(
                        f"{self.BASE_URL}/execution/{execution_id}/status",
                        headers=self.headers
                    )
                    
                    # Handle rate limit
                    if status_response.status_code == 429:
                        print(f"  ⚠️  Rate limited, waiting 5 seconds...")
                        await asyncio.sleep(5)
                        continue
                    
                    status_response.raise_for_status()
                    status = status_response.json()
                    
                    if status["state"] == "QUERY_STATE_COMPLETED":
                        break
                    elif status["state"] in ["QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"]:
                        raise Exception(f"Query failed: {status}")
                    
                    await asyncio.sleep(1)
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        print(f"  ⚠️  Rate limited on attempt {attempt+1}, waiting...")
                        await asyncio.sleep(5)
                        continue
                    raise
            
            # Get results
            results_response = await client.get(
                f"{self.BASE_URL}/execution/{execution_id}/results",
                headers=self.headers
            )
            results_response.raise_for_status()
            return results_response.json()
    
    async def get_ousg_supply(self) -> float:
        """Get current OUSG total supply"""
        result = await self.execute_query(query_id=6884965)
        if "result" not in result or "rows" not in result["result"]:
            raise Exception(f"Invalid response structure: {result}")
        return result["result"]["rows"][0]["current_supply"]
    
    async def get_usdy_supply(self) -> float:
        """Get current USDY total supply"""
        result = await self.execute_query(query_id=6884969)
        if "result" not in result or "rows" not in result["result"]:
            raise Exception(f"Invalid response structure: {result}")
        return result["result"]["rows"][0]["current_supply"]
    
    async def get_unique_holders(self, days: int = 7) -> int:
        """Get unique holders count - uses latest from holders trend query"""
        try:
            # Use the holders trend query and get the most recent count
            result = await self.execute_query(query_id=6885440)
            
            # Check if result has proper structure
            if not isinstance(result, dict):
                print(f"  ⚠️  Unexpected result type: {type(result)}")
                return 0
            
            if "result" not in result:
                print(f"  ⚠️  No 'result' key in response. Keys: {result.keys()}")
                return 0
            
            if "rows" not in result["result"]:
                print(f"  ⚠️  No 'rows' in result. Keys: {result['result'].keys()}")
                return 0
            
            rows = result["result"]["rows"]
            if not rows:
                print(f"  ⚠️  Empty rows returned")
                return 0
            
            # Sum holders from both tokens for the most recent day
            total_holders = 0
            latest_day = None
            
            for row in rows:
                day = row.get("day", "")
                if latest_day is None:
                    latest_day = day
                
                # Only count holders from the latest day
                if day == latest_day and "total_holders" in row:
                    total_holders += int(row["total_holders"])
            
            print(f"  ℹ️  Total holders from both tokens: {total_holders}")
            return total_holders
                
        except Exception as e:
            print(f"  ✗ Error fetching holders: {str(e)}")
            return 0
    
    async def get_transfer_volume(self, days: int = 30) -> list[dict]:
        """Get daily transfer volume"""
        result = await self.execute_query(query_id=6884981)
        if "result" not in result or "rows" not in result["result"]:
            raise Exception(f"Invalid response structure: {result}")
        return result["result"]["rows"]
    
    async def get_whale_holders(self, limit: int = 10) -> list[dict]:
        """Get top whale holders for both tokens"""
        # Query OUSG whales
        ousg_result = await self.execute_query(query_id=6885322)
        ousg_whales = ousg_result["result"]["rows"]
        
        await asyncio.sleep(5)  # Rate limit delay
        
        # Query USDY whales
        usdy_result = await self.execute_query(query_id=6886806)
        usdy_whales = usdy_result["result"]["rows"]
        
        # Combine results
        all_whales = ousg_whales + usdy_whales
        return all_whales
    
    async def get_nav_deviation(self, days: int = 30) -> list[dict]:
        """Get NAV deviation history"""
        result = await self.execute_query(query_id=6885325)
        return result["result"]["rows"]
    
    async def get_tvl(self) -> float:
        """Get total value locked (OUSG + USDY)"""
        ousg = await self.get_ousg_supply()
        usdy = await self.get_usdy_supply()
        return ousg + usdy
    
    async def get_apy_history(self, days: int = 30) -> list[dict]:
        """Get APY history for last N days"""
        result = await self.execute_query(query_id=6885354)
        return result["result"]["rows"]
    
    async def get_concentration_ratio(self, days: int = 30) -> list[dict]:
        """Get top 10 holders concentration ratio over time"""
        result = await self.execute_query(query_id=6885355)
        return result["result"]["rows"]
    
    async def get_daily_active_addresses(self, days: int = 30) -> list[dict]:
        """Get daily active addresses"""
        result = await self.execute_query(query_id=6885358)
        return result["result"]["rows"]
    
    async def get_transfer_count_trend(self, days: int = 30) -> list[dict]:
        """Get transfer count and volume trend"""
        result = await self.execute_query(query_id=6885363)
        return result["result"]["rows"]
    
    async def get_holders_trend(self, days: int = 30) -> list[dict]:
        """Get total holders trend over time"""
        result = await self.execute_query(query_id=6885440)
        if "result" not in result or "rows" not in result["result"]:
            raise Exception(f"Invalid response structure: {result}")
        return result["result"]["rows"]
    
    async def get_large_transfers(self, days: int = 30) -> list[dict]:
        """Get all large transfers (>$100K) for last 30 days"""
        result = await self.execute_query(query_id=6892674)
        if "result" not in result or "rows" not in result["result"]:
            raise Exception(f"Invalid response structure: {result}")
        return result["result"]["rows"]


dune_client = DuneClient()
