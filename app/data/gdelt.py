from gdeltdoc import GdeltDoc, Filters
from datetime import datetime, timedelta
from typing import List
import asyncio


class GDELTClient:
    """Client for GDELT 2.0 Doc API using official gdeltdoc library"""
    
    def __init__(self):
        self.gd = GdeltDoc()
    
    async def search_events(
        self,
        keywords: List[str] = None,
        hours: int = 24,
        max_records: int = 20
    ) -> List[dict]:
        """Search for relevant events using GDELT 2.0 Doc API"""
        
        # Default keywords for RWA/Treasury/Crypto monitoring
        # Using broader, simpler terms that GDELT can find
        if not keywords:
            keywords = [
                "federal reserve",
                "treasury",
                "cryptocurrency",
                "stablecoin",
                "SEC crypto"
            ]
        
        events = []
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=hours)
        
        # Search for each keyword
        for keyword in keywords:
            try:
                # Run in thread pool since gdeltdoc is synchronous
                articles = await asyncio.to_thread(
                    self._search_keyword,
                    keyword,
                    start_date,
                    end_date,
                    max_records // len(keywords)
                )
                
                # Check if we got results
                if articles is None or articles.empty:
                    print(f"  ℹ️  No results for '{keyword}'")
                    continue
                
                for _, article in articles.iterrows():
                    tags = self._classify_event(article.get("title", ""))
                    
                    events.append({
                        "id": article.get("url", f"gdelt_{len(events)}"),
                        "title": article.get("title", ""),
                        "source": article.get("domain", "Unknown"),
                        "url": article.get("url", ""),
                        "published_at": article.get("seendate", datetime.now().isoformat()),
                        "tags": tags,
                        "lat": None,
                        "lon": None
                    })
                    
                    if len(events) >= max_records:
                        break
                
                if len(events) >= max_records:
                    break
                    
            except Exception as e:
                print(f"  ⚠️  GDELT keyword '{keyword}' error: {str(e)}")
                import traceback
                print(f"  📋 Full traceback:")
                traceback.print_exc()
                continue
        
        print(f"  ✓ GDELT returned {len(events)} events")
        return events[:max_records]
    
    def _search_keyword(self, keyword: str, start_date: datetime, end_date: datetime, num_records: int):
        """Synchronous search for a single keyword"""
        try:
            # Use timespan instead of exact dates - GDELT works better with this
            f = Filters(
                keyword=keyword,
                timespan="1d",  # Last 24 hours
                num_records=min(num_records, 250)  # API limit
            )
            
            result = self.gd.article_search(f)
            return result
        except Exception as e:
            print(f"    ⚠️  Search failed for '{keyword}': {e}")
            return None
    
    def _classify_event(self, title: str) -> List[str]:
        """Classify event into tags based on keywords"""
        title_lower = title.lower()
        tags = []
        
        if any(kw in title_lower for kw in ["fed", "federal reserve", "interest rate", "fomc"]):
            tags.append("FED")
        
        if any(kw in title_lower for kw in ["sec", "regulation", "mica", "regulatory", "cftc"]):
            tags.append("REG")
        
        if any(kw in title_lower for kw in ["war", "conflict", "sanction", "geopolit"]):
            tags.append("GEO")
        
        if any(kw in title_lower for kw in ["market", "crypto", "bitcoin", "ethereum", "treasury"]):
            tags.append("MARKET")
        
        return tags or ["OTHER"]


gdelt_client = GDELTClient()
