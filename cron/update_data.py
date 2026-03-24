#!/usr/bin/env python3
"""
Periodic data refresh script
Run via cron/systemd timer every 30 minutes
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.dune import dune_client
from app.data.gdelt import gdelt_client
from app.data.cache import cache
from app.data.health import health_monitor


async def update_metrics():
    """Fetch and cache Ondo metrics from Dune"""
    print("Fetching Dune metrics...")
    
    try:
        # Fetch OUSG supply
        print("  Fetching OUSG supply...")
        start_time = asyncio.get_event_loop().time()
        ousg_supply = await dune_client.get_ousg_supply()
        latency = (asyncio.get_event_loop().time() - start_time) * 1000
        await cache.set_metric("ousg_supply", ousg_supply)
        health_monitor.record_update("dune_ousg", latency)
        print(f"✓ OUSG Supply: ${ousg_supply:,.2f}")
        await asyncio.sleep(5)  # Increased delay for rate limit
        
        # Fetch USDY supply
        print("  Fetching USDY supply...")
        start_time = asyncio.get_event_loop().time()
        usdy_supply = await dune_client.get_usdy_supply()
        latency = (asyncio.get_event_loop().time() - start_time) * 1000
        await cache.set_metric("usdy_supply", usdy_supply)
        health_monitor.record_update("dune_usdy", latency)
        print(f"✓ USDY Supply: ${usdy_supply:,.2f}")
        await asyncio.sleep(5)  # Increased delay for rate limit
        
        # Fetch unique holders
        print("  Fetching unique holders...")
        start_time = asyncio.get_event_loop().time()
        holders = await dune_client.get_unique_holders(days=7)
        latency = (asyncio.get_event_loop().time() - start_time) * 1000
        await cache.set_metric("unique_holders_7d", holders)
        health_monitor.record_update("dune_holders", latency)
        if holders > 0:
            print(f"✓ Unique Holders (7d): {holders}")
        else:
            print(f"⚠️  Unique Holders: No data returned")
        await asyncio.sleep(5)  # Increased delay for rate limit
        
        # Fetch transfer volume (may fail due to rate limit)
        print("  Fetching transfer volume...")
        try:
            start_time = asyncio.get_event_loop().time()
            volume = await dune_client.get_transfer_volume(days=30)
            latency = (asyncio.get_event_loop().time() - start_time) * 1000
            await cache.set_metric("transfer_volume_30d", volume)
            health_monitor.record_update("dune_volume", latency)
            print(f"✓ Transfer Volume: {len(volume)} days")
        except Exception as e:
            health_monitor.record_error("dune_volume")
            print(f"⚠️  Transfer volume skipped (rate limit): {str(e)[:100]}")
        
        # Fetch whale holders
        print("  Fetching whale holders...")
        try:
            whales = await dune_client.get_whale_holders(limit=10)
            await cache.set_metric("whale_holders", whales)
            print(f"✓ Whale Holders: {len(whales)} tracked")
        except Exception as e:
            print(f"⚠️  Whale holders skipped: {str(e)[:100]}")
        
        # Fetch APY history
        print("  Fetching APY history...")
        try:
            apy_history = await dune_client.get_apy_history(days=30)
            await cache.set_metric("apy_history", apy_history)
            print(f"✓ APY History: {len(apy_history)} days")
        except Exception as e:
            print(f"⚠️  APY history skipped: {str(e)[:100]}")
        
        # Fetch concentration ratio
        print("  Fetching concentration ratio...")
        try:
            concentration = await dune_client.get_concentration_ratio(days=30)
            await cache.set_metric("concentration_ratio", concentration)
            print(f"✓ Concentration Ratio: {len(concentration)} days")
        except Exception as e:
            print(f"⚠️  Concentration ratio skipped: {str(e)[:100]}")
        
        # Fetch daily active addresses
        print("  Fetching daily active addresses...")
        try:
            active_addresses = await dune_client.get_daily_active_addresses(days=30)
            await cache.set_metric("daily_active_addresses", active_addresses)
            print(f"✓ Daily Active Addresses: {len(active_addresses)} days")
        except Exception as e:
            print(f"⚠️  Daily active addresses skipped: {str(e)[:100]}")
        
        # Fetch transfer count trend
        print("  Fetching transfer count trend...")
        try:
            transfer_trend = await dune_client.get_transfer_count_trend(days=30)
            await cache.set_metric("transfer_count_trend", transfer_trend)
            print(f"✓ Transfer Count Trend: {len(transfer_trend)} days")
        except Exception as e:
            print(f"⚠️  Transfer count trend skipped: {str(e)[:100]}")
        
        # Fetch holders trend
        print("  Fetching holders trend...")
        try:
            holders_trend = await dune_client.get_holders_trend(days=30)
            await cache.set_metric("holders_trend", holders_trend)
            print(f"✓ Holders Trend: {len(holders_trend)} days")
        except Exception as e:
            print(f"⚠️  Holders trend skipped: {str(e)[:100]}")
        
    except NotImplementedError as e:
        print(f"⚠️  Dune queries not configured: {e}")
        print("   Skipping metrics update. Configure queries in app/data/dune.py")
    except Exception as e:
        health_monitor.record_error("dune_ousg")
        health_monitor.record_error("dune_usdy")
        health_monitor.record_error("dune_holders")
        print(f"✗ Dune API error: {e}")
        import traceback
        traceback.print_exc()


async def update_events():
    """Fetch and cache events from GDELT"""
    print("\nFetching GDELT events...")
    
    try:
        start_time = asyncio.get_event_loop().time()
        events = await gdelt_client.search_events(hours=24, max_records=20)
        latency = (asyncio.get_event_loop().time() - start_time) * 1000
        
        for event in events:
            await cache.add_event(event)
        
        health_monitor.record_update("gdelt_events", latency)
        print(f"✓ Cached {len(events)} events")
        
    except Exception as e:
        health_monitor.record_error("gdelt_events")
        print(f"✗ GDELT API error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main update routine"""
    print("=" * 50)
    print("Sirex RWA Dashboard - Data Update")
    print("=" * 50)
    
    # Initialize database
    await cache.init_db()
    
    # Update all data sources
    await update_metrics()
    await update_events()
    
    print("\n" + "=" * 50)
    print("Update complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
