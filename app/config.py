from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application configuration"""
    
    # API Keys
    dune_api_key: str = ""
    alchemy_api_key: str = ""
    openrouter_api_key: str = ""
    arkham_api_key: str = ""
    
    # Database
    database_path: str = "data/cache.db"
    
    # Cache settings
    cache_ttl_minutes: int = 30
    
    # Ondo contract addresses (Ethereum mainnet)
    ousg_contract: str = "0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92"
    usdy_contract: str = "0x96F6eF951840721AdBF46Ac996b59E0235CB985C"
    
    # GDELT settings
    gdelt_keywords: list[str] = [
        "treasury bond", "federal reserve", "interest rate",
        "SEC crypto", "tokenization", "real world asset",
        "stablecoin", "BlackRock", "Ondo", "BUIDL"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
