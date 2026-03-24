import httpx
from app.config import settings


class AlchemyClient:
    """Client for Alchemy API"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.alchemy_api_key
        self.base_url = f"https://eth-mainnet.g.alchemy.com/v2/{self.api_key}"
    
    async def get_token_price(self, token_address: str) -> float:
        """Get token price in USD"""
        # Alchemy doesn't provide direct price API
        # This would typically use a DEX aggregator or price oracle
        # Placeholder implementation
        return 0.0
    
    async def get_token_balance(self, token_address: str, wallet_address: str) -> float:
        """Get token balance for a wallet"""
        async with httpx.AsyncClient() as client:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {
                        "to": token_address,
                        "data": f"0x70a08231000000000000000000000000{wallet_address[2:]}"
                    },
                    "latest"
                ],
                "id": 1
            }
            
            response = await client.post(self.base_url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # Convert hex to decimal
            balance_hex = result.get("result", "0x0")
            balance = int(balance_hex, 16) / 10**18  # Assuming 18 decimals
            
            return balance


alchemy_client = AlchemyClient()
