"""
Data Health Monitor - tracks freshness and quality of data sources
Inspired by Shadowbroker's data freshness tracking
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio


class DataHealthMonitor:
    """Monitor health and freshness of data sources"""
    
    def __init__(self):
        self._last_updates: Dict[str, datetime] = {}
        self._error_counts: Dict[str, int] = {}
        self._latencies: Dict[str, float] = {}
    
    def record_update(self, source: str, latency_ms: float = 0):
        """Record successful data update"""
        self._last_updates[source] = datetime.utcnow()
        self._latencies[source] = latency_ms
        self._error_counts[source] = 0
    
    def record_error(self, source: str):
        """Record failed data update"""
        self._error_counts[source] = self._error_counts.get(source, 0) + 1
    
    def get_source_health(self, source: str) -> Dict:
        """Get health status for a specific source"""
        last_update = self._last_updates.get(source)
        
        if not last_update:
            return {
                "status": "unknown",
                "message": "No data received yet",
                "last_update": None,
                "age_seconds": None,
                "latency_ms": None,
                "error_count": 0
            }
        
        age = (datetime.utcnow() - last_update).total_seconds()
        error_count = self._error_counts.get(source, 0)
        latency = self._latencies.get(source, 0)
        
        # Determine status based on age and errors
        if error_count > 3:
            status = "critical"
            message = f"Multiple failures ({error_count} errors)"
        elif age > 3600:  # 1 hour
            status = "stale"
            message = f"Data is {int(age/60)} minutes old"
        elif age > 1800:  # 30 minutes
            status = "warning"
            message = f"Data is {int(age/60)} minutes old"
        else:
            status = "healthy"
            message = "Data is fresh"
        
        return {
            "status": status,
            "message": message,
            "last_update": last_update.isoformat(),
            "age_seconds": int(age),
            "latency_ms": latency,
            "error_count": error_count
        }
    
    def get_all_health(self) -> Dict:
        """Get health status for all sources"""
        sources = [
            "dune_ousg",
            "dune_usdy", 
            "dune_holders",
            "dune_volume",
            "gdelt_events"
        ]
        
        health_data = {}
        for source in sources:
            health_data[source] = self.get_source_health(source)
        
        # Calculate overall health
        statuses = [h["status"] for h in health_data.values()]
        if "critical" in statuses:
            overall = "critical"
        elif "stale" in statuses:
            overall = "degraded"
        elif "warning" in statuses:
            overall = "warning"
        else:
            overall = "healthy"
        
        return {
            "overall_status": overall,
            "sources": health_data,
            "timestamp": datetime.utcnow().isoformat()
        }


# Global instance
health_monitor = DataHealthMonitor()
