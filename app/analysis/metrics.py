from typing import Dict, List


def calculate_nav_deviation(token_price: float, nav: float) -> float:
    """
    Calculate NAV deviation percentage
    Formula: (Token_Price - NAV) / NAV × 100%
    """
    if nav == 0:
        return 0.0
    return ((token_price - nav) / nav) * 100


def calculate_whale_score(
    top_holders: List[Dict],
    total_supply: float
) -> float:
    """
    Calculate whale concentration score
    Higher score = more concentrated holdings
    """
    if not top_holders or total_supply == 0:
        return 0.0
    
    top_10_total = sum(h.get("balance", 0) for h in top_holders[:10])
    concentration = (top_10_total / total_supply) * 100
    
    return round(concentration, 2)


def calculate_stress_level(event_count: int, negative_count: int) -> str:
    """
    Calculate market stress level based on event analysis
    Returns: "LOW", "MEDIUM", or "HIGH"
    """
    if event_count == 0:
        return "LOW"
    
    negative_ratio = negative_count / event_count
    
    if negative_ratio > 0.6 or event_count > 15:
        return "HIGH"
    elif negative_ratio > 0.3 or event_count > 8:
        return "MEDIUM"
    else:
        return "LOW"


def format_supply_change(current: float, previous: float) -> Dict:
    """Format supply change with percentage and direction"""
    if previous == 0:
        return {"change": 0, "percent": 0, "direction": "neutral"}
    
    change = current - previous
    percent = (change / previous) * 100
    
    return {
        "change": round(change, 2),
        "percent": round(percent, 2),
        "direction": "up" if change > 0 else "down" if change < 0 else "neutral"
    }
