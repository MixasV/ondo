"""
Token price fetching from CoinGecko API
"""
import httpx
from typing import Optional


class PriceClient:
    """Client for fetching token prices"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # Token contract addresses to CoinGecko IDs
    TOKEN_IDS = {
        "0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92": "ondo-us-dollar-yield",  # OUSG
        "0x96F6eF951840721AdBF46Ac996b59E0235CB985C": "ondo-us-dollar-yield",  # USDY
    }
    
    async def get_token_price(self, token_address: str) -> Optional[float]:
        """Get token price in USD from CoinGecko
        
        Args:
            token_address: Ethereum token contract address
            
        Returns:
            Price in USD or None if not found
        """
        # Get CoinGecko ID for token
        token_id = self.TOKEN_IDS.get(token_address)
        if not token_id:
            # Try to get price by contract address
            return await self._get_price_by_contract(token_address)
        
        # Get price by CoinGecko ID
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/simple/price",
                    params={
                        "ids": token_id,
                        "vs_currencies": "usd"
                    }
                )
                
                if response.status_code == 404:
                    return None
                
                response.raise_for_status()
                data = response.json()
                
                return data.get(token_id, {}).get("usd")
                
        except Exception as e:
            print(f"  ⚠️  CoinGecko price fetch failed for {token_address[:10]}...: {e}")
            return None
    
    async def _get_price_by_contract(self, token_address: str) -> Optional[float]:
        """Get token price by contract address from CoinGecko
        
        Args:
            token_address: Ethereum token contract address
            
        Returns:
            Price in USD or None if not found
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/simple/token_price/ethereum",
                    params={
                        "contract_addresses": token_address,
                        "vs_currencies": "usd"
                    }
                )
                
                if response.status_code == 404:
                    return None
                
                response.raise_for_status()
                data = response.json()
                
                return data.get(token_address.lower(), {}).get("usd")
                
        except Exception as e:
            print(f"  ⚠️  CoinGecko contract price fetch failed: {e}")
            return None
    
    async def get_nav_deviation(self, token_address: str, nav_value: float = 1.0) -> Optional[float]:
        """Calculate NAV deviation for a token
        
        Args:
            token_address: Ethereum token contract address
            nav_value: Net Asset Value per token (default 1.0 for stablecoins)
            
        Returns:
            Deviation percentage (positive = premium, negative = discount)
            None if price not available
        """
        market_price = await self.get_token_price(token_address)
        
        if market_price is None:
            return None
        
        # Calculate deviation: (market_price - nav) / nav * 100
        deviation = ((market_price - nav_value) / nav_value) * 100
        
        return deviation


# Global instance
price_client = PriceClient()
