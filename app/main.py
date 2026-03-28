from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime
import json

from app.data.cache import cache
from app.data.dune import dune_client
from app.data.gdelt import gdelt_client
from app.data.arkham import arkham_client
from app.data.prices import price_client
from app.data.health import health_monitor
from app.analysis.simulation import simulation_engine
from app.analysis.metrics import calculate_stress_level
from app.analysis.commentary import commentary_generator
import asyncio

app = FastAPI(title="Sirex RWA Dashboard")

# Setup templates and static files
templates = Jinja2Templates(directory="app/templates")

# Add custom Jinja filters
def from_json_filter(value):
    """Parse JSON string to Python object"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return []
    return value

templates.env.filters['from_json'] = from_json_filter

Path("app/static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await cache.init_db()
    
    # Restore health monitor state from cache
    print("🔄 Restoring health monitor state...")
    try:
        # Check each metric and restore health status
        metrics_to_check = [
            ("ousg_supply", "dune_ousg"),
            ("usdy_supply", "dune_usdy"),
            ("unique_holders_7d", "dune_holders"),
            ("transfer_volume_30d", "dune_volume"),
        ]
        
        for metric_key, health_key in metrics_to_check:
            value = await cache.get_metric(metric_key, max_age_minutes=60)
            if value is not None:
                # Metric exists and is relatively fresh, mark as healthy
                health_monitor.record_update(health_key, latency_ms=0)
        
        # Check events
        events = await cache.get_recent_events(hours=24, limit=1)
        if events:
            health_monitor.record_update("gdelt_events", latency_ms=0)
        
        print("✓ Health monitor restored")
    except Exception as e:
        print(f"⚠️  Could not restore health monitor: {e}")
    
    # Start background task for periodic updates
    asyncio.create_task(periodic_update_task())


async def periodic_update_task():
    """Background task that runs data updates every hour"""
    # Wait 5 minutes after startup before first update
    await asyncio.sleep(300)
    
    while True:
        try:
            print("🔄 Starting scheduled data update...")
            await update_all_data()
            print("✓ Scheduled update complete")
        except Exception as e:
            print(f"✗ Scheduled update error: {e}")
            import traceback
            traceback.print_exc()
        
        # Wait 1 hour before next update
        await asyncio.sleep(3600)


# Lock to prevent multiple simultaneous updates
_update_lock = asyncio.Lock()


async def update_all_data():
    """Update all metrics and events from APIs"""
    
    # Try to acquire lock, return immediately if already locked
    if _update_lock.locked():
        print("⚠️  Update already in progress, skipping...")
        return
    
    async with _update_lock:
        print(f"🔄 Starting data update at {datetime.now().strftime('%H:%M:%S')}")
        
        # Clear completion flag at start
        await cache.set_metric("data_update_complete", False)
        
        # Define total stages
        total_stages = 12  # OUSG, USDY, Holders, Whales, Holders Trend, Concentration, Active Addresses, Transfer Trend, APY, NAV, Large Transfers, GDELT Events
        current_stage = 0
        
        try:
            print("🔄 Auto-updating data...")
            
            # Update Dune metrics
            try:
                # Stage 1: OUSG Supply
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching OUSG supply")
                start_time = asyncio.get_event_loop().time()
                ousg = await dune_client.get_ousg_supply()
                latency = (asyncio.get_event_loop().time() - start_time) * 1000
                await cache.set_metric("ousg_supply", ousg)
                health_monitor.record_update("dune_ousg", latency)
                print(f"✓ OUSG: ${ousg:,.2f}")
                await asyncio.sleep(5)
                
                # Stage 2: USDY Supply
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching USDY supply")
                start_time = asyncio.get_event_loop().time()
                usdy = await dune_client.get_usdy_supply()
                latency = (asyncio.get_event_loop().time() - start_time) * 1000
                await cache.set_metric("usdy_supply", usdy)
                health_monitor.record_update("dune_usdy", latency)
                print(f"✓ USDY: ${usdy:,.2f}")
                await asyncio.sleep(5)
                
                # Stage 3: Unique Holders
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching unique holders")
                start_time = asyncio.get_event_loop().time()
                holders = await dune_client.get_unique_holders()
                latency = (asyncio.get_event_loop().time() - start_time) * 1000
                await cache.set_metric("unique_holders_7d", holders)
                health_monitor.record_update("dune_holders", latency)
                print(f"✓ Holders: {holders}")
                await asyncio.sleep(5)
                
                # Stage 4: Whale Holders
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching whale holders")
                try:
                    start_time = asyncio.get_event_loop().time()
                    whale_holders = await dune_client.get_whale_holders()
                    latency = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    # Enrich with Arkham labels
                    whale_holders = await arkham_client.enrich_whale_holders(whale_holders)
                    
                    await cache.set_metric("whale_holders", whale_holders)
                    print(f"✓ Whales: {len(whale_holders)}")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"⚠️  Whales skipped: {str(e)[:50]}")
                
                # Stage 5: Holders Trend
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching holders trend")
                try:
                    start_time = asyncio.get_event_loop().time()
                    holders_trend = await dune_client.get_holders_trend()
                    latency = (asyncio.get_event_loop().time() - start_time) * 1000
                    await cache.set_metric("holders_trend", holders_trend)
                    print(f"✓ Holders trend: {len(holders_trend)} days")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"⚠️  Holders trend skipped: {str(e)[:50]}")
                
                # Stage 6: Concentration Ratio
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching concentration ratio")
                try:
                    start_time = asyncio.get_event_loop().time()
                    concentration = await dune_client.get_concentration_ratio()
                    latency = (asyncio.get_event_loop().time() - start_time) * 1000
                    await cache.set_metric("concentration_ratio", concentration)
                    print(f"✓ Concentration: {len(concentration)} days")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"⚠️  Concentration skipped: {str(e)[:50]}")
                
                # Stage 7: Daily Active Addresses
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching active addresses")
                try:
                    start_time = asyncio.get_event_loop().time()
                    daily_active = await dune_client.get_daily_active_addresses()
                    latency = (asyncio.get_event_loop().time() - start_time) * 1000
                    await cache.set_metric("daily_active_addresses", daily_active)
                    print(f"✓ Active addresses: {len(daily_active)} days")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"⚠️  Active addresses skipped: {str(e)[:50]}")
                
                # Stage 8: Transfer Trend
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching transfer trend")
                try:
                    start_time = asyncio.get_event_loop().time()
                    transfer_trend = await dune_client.get_transfer_count_trend()
                    latency = (asyncio.get_event_loop().time() - start_time) * 1000
                    await cache.set_metric("transfer_count_trend", transfer_trend)
                    health_monitor.record_update("dune_volume", latency)
                    print(f"✓ Transfer trend: {len(transfer_trend)} days")
                    await asyncio.sleep(5)
                except Exception as e:
                    health_monitor.record_error("dune_volume")
                    print(f"⚠️  Transfer trend skipped: {str(e)[:50]}")
                
                # Stage 9: APY History
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching APY history")
                try:
                    start_time = asyncio.get_event_loop().time()
                    apy_history = await dune_client.get_apy_history()
                    latency = (asyncio.get_event_loop().time() - start_time) * 1000
                    await cache.set_metric("apy_history", apy_history)
                    print(f"✓ APY history: {len(apy_history)} days")
                except Exception as e:
                    print(f"⚠️  APY skipped: {str(e)[:50]}")
                
                # Stage 10: NAV Deviation
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Calculating NAV deviation")
                try:
                    # USDY NAV deviation (more liquid, traded on DEXes)
                    usdy_deviation = await price_client.get_nav_deviation(
                        "0x96F6eF951840721AdBF46Ac996b59E0235CB985C",
                        nav_value=1.0
                    )
                    if usdy_deviation is not None:
                        await cache.set_metric("nav_deviation", usdy_deviation)
                        print(f"✓ NAV deviation: {usdy_deviation:.2f}%")
                    else:
                        # Default to 0 if price not available
                        await cache.set_metric("nav_deviation", 0.0)
                        print(f"ℹ️  NAV deviation: using default 0%")
                except Exception as e:
                    await cache.set_metric("nav_deviation", 0.0)
                    print(f"⚠️  NAV deviation skipped: {str(e)[:50]}")
                
                # Stage 11: Large Transfers
                current_stage += 1
                await cache.set_update_progress(current_stage, total_stages, "Fetching large transfers")
                try:
                    start_time = asyncio.get_event_loop().time()
                    large_transfers = await dune_client.get_large_transfers()
                    latency = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    # Extract unique addresses
                    addresses = set()
                    for transfer in large_transfers:
                        from_addr = transfer.get('from_address')
                        to_addr = transfer.get('to_address')
                        if from_addr:
                            addresses.add(from_addr)
                        if to_addr:
                            addresses.add(to_addr)
                    
                    # Enrich with Arkham labels
                    if addresses:
                        print(f"🏷️  Enriching {len(addresses)} addresses from large transfers...")
                        labels = await arkham_client.get_labels_for_addresses(list(addresses))
                        
                        # Add labels to transfers
                        for transfer in large_transfers:
                            from_addr = transfer.get('from_address')
                            to_addr = transfer.get('to_address')
                            
                            from_label = labels.get(from_addr, {})
                            to_label = labels.get(to_addr, {})
                            
                            transfer['from_label'] = from_label.get('label') if from_label else None
                            transfer['from_entity_type'] = from_label.get('entity_type') if from_label else None
                            transfer['to_label'] = to_label.get('label') if to_label else None
                            transfer['to_entity_type'] = to_label.get('entity_type') if to_label else None
                    
                    await cache.set_metric("large_transfers", large_transfers)
                    print(f"✓ Large transfers: {len(large_transfers)} transfers")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"⚠️  Large transfers skipped: {str(e)[:50]}")
                
                print("✓ Dune metrics updated")
                
                # Generate AI commentary after successful data update - read from DB
                try:
                    print("🤖 Generating AI commentary...")
                    
                    ousg = await cache.get_metric("ousg_supply") or 0
                    usdy = await cache.get_metric("usdy_supply") or 0
                    holders = await cache.get_metric("unique_holders_7d") or 0
                    events = await cache.get_recent_events(hours=24, limit=20)
                    whale_holders = await cache.get_metric("whale_holders") or []
                    holders_trend = await cache.get_metric("holders_trend") or []
                    concentration_ratio = await cache.get_metric("concentration_ratio") or []
                    apy_history = await cache.get_metric("apy_history") or []
                    nav_deviation = await cache.get_metric("nav_deviation") or 0
                    transfer_trend = await cache.get_metric("transfer_count_trend") or []
                    daily_active = await cache.get_metric("daily_active_addresses") or []
                    large_transfers = await cache.get_metric("large_transfers") or []
                    
                    commentary = await commentary_generator.generate_commentary(
                        ousg_supply=ousg,
                        usdy_supply=usdy,
                        holders=holders,
                        events=events,
                        whale_holders=whale_holders,
                        holders_trend=holders_trend,
                        concentration_ratio=concentration_ratio,
                        apy_history=apy_history,
                        nav_deviation=nav_deviation,
                        transfer_trend=transfer_trend,
                        daily_active=daily_active,
                        large_transfers=large_transfers,
                        force=True
                    )
                    
                    print(f"✓ AI commentary generated")
                except Exception as e:
                    print(f"⚠️  Commentary generation failed: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Mark data update as complete AFTER everything is done
                await cache.set_metric("data_update_complete", True)
                
            except Exception as e:
                health_monitor.record_error("dune_ousg")
                health_monitor.record_error("dune_usdy")
                health_monitor.record_error("dune_holders")
                print(f"✗ Dune update error: {e}")
                import traceback
                traceback.print_exc()
                # Still mark as complete so page doesn't hang
                await cache.set_metric("data_update_complete", True)
            
            # Stage 12: GDELT Events
            current_stage += 1
            await cache.set_update_progress(current_stage, total_stages, "Fetching GDELT events")
            try:
                start_time = asyncio.get_event_loop().time()
                events = await gdelt_client.search_events(hours=24, max_records=20)
                latency = (asyncio.get_event_loop().time() - start_time) * 1000
                for event in events:
                    await cache.add_event(event)
                health_monitor.record_update("gdelt_events", latency)
                print(f"✓ GDELT events updated ({len(events)} events)")
            except Exception as e:
                health_monitor.record_error("gdelt_events")
                print(f"✗ GDELT update error: {e}")
            
            # Clear progress after completion
            await cache.set_update_progress(total_stages, total_stages, "Complete")
            print(f"✓ Data update complete at {datetime.now().strftime('%H:%M:%S')}")
        
        except Exception as e:
            print(f"❌ Fatal error in update_all_data: {e}")
            import traceback
            traceback.print_exc()


async def check_and_update_cache():
    """Check if cache needs updating and trigger update if needed"""
    # Check if we have basic metrics and their age
    ousg = await cache.get_metric("ousg_supply", max_age_minutes=120)  # 2 hours
    usdy = await cache.get_metric("usdy_supply", max_age_minutes=120)
    holders = await cache.get_metric("unique_holders_7d", max_age_minutes=120)
    
    # If critical data is missing, block and update
    if ousg is None or usdy is None or holders is None:
        print("⚠️  Critical data missing, blocking for update...")
        await update_all_data()
        return False
    
    # Check if data is older than 1 hour - trigger background update
    ousg_fresh = await cache.get_metric("ousg_supply", max_age_minutes=60)
    if ousg_fresh is None and not _update_lock.locked():
        print("ℹ️  Data is stale (>1 hour), triggering background update...")
        asyncio.create_task(update_all_data())
    
    return True


@app.get("/")
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )


@app.get("/api/metrics")
async def get_metrics():
    """Get Ondo Pulse metrics from cache"""
    try:
        ousg_supply = await cache.get_metric("ousg_supply", max_age_minutes=120) or 0
        usdy_supply = await cache.get_metric("usdy_supply", max_age_minutes=120) or 0
        unique_holders = await cache.get_metric("unique_holders_7d", max_age_minutes=120) or 0
        nav_deviation = await cache.get_metric("nav_deviation", max_age_minutes=120) or 0
        whale_holders = await cache.get_metric("whale_holders", max_age_minutes=120) or []
        holders_trend = await cache.get_metric("holders_trend", max_age_minutes=120) or []
        concentration_ratio = await cache.get_metric("concentration_ratio", max_age_minutes=120) or []
        daily_active = await cache.get_metric("daily_active_addresses", max_age_minutes=120) or []
        transfer_trend = await cache.get_metric("transfer_count_trend", max_age_minutes=120) or []
        apy_history = await cache.get_metric("apy_history", max_age_minutes=120) or []
        
        # Get actual timestamp of last update
        last_update = await cache.get_metric_timestamp("ousg_supply")
        timestamp = last_update.isoformat() if last_update else datetime.now().isoformat()
        
        return {
            "ousg_supply": ousg_supply,
            "usdy_supply": usdy_supply,
            "unique_holders_7d": unique_holders,
            "nav_deviation": nav_deviation,
            "whale_holders": whale_holders,
            "holders_trend": holders_trend,
            "concentration_ratio": concentration_ratio,
            "daily_active_addresses": daily_active,
            "transfer_count_trend": transfer_trend,
            "apy_history": apy_history,
            "timestamp": timestamp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/partials/metrics")
async def get_metrics_html(request: Request):
    """Get Ondo Pulse metrics as HTML"""
    try:
        # Check if cache needs updating
        cache_ready = await check_and_update_cache()
        
        ousg_supply = await cache.get_metric("ousg_supply", max_age_minutes=120)
        usdy_supply = await cache.get_metric("usdy_supply", max_age_minutes=120)
        
        # If no data yet, show loading screen
        if ousg_supply is None or usdy_supply is None:
            return templates.TemplateResponse("loading.html", {"request": request})
        
        unique_holders = await cache.get_metric("unique_holders_7d", max_age_minutes=120) or 0
        nav_deviation = await cache.get_metric("nav_deviation", max_age_minutes=120) or 0
        transfer_volume = await cache.get_metric("transfer_volume_30d", max_age_minutes=120) or []
        whale_holders = await cache.get_metric("whale_holders", max_age_minutes=120) or []
        apy_history = await cache.get_metric("apy_history", max_age_minutes=120) or []
        concentration_ratio = await cache.get_metric("concentration_ratio", max_age_minutes=120) or []
        daily_active = await cache.get_metric("daily_active_addresses", max_age_minutes=120) or []
        transfer_trend = await cache.get_metric("transfer_count_trend", max_age_minutes=120) or []
        holders_trend = await cache.get_metric("holders_trend", max_age_minutes=120) or []
        tvl = ousg_supply + usdy_supply
        
        # Check if update is in progress
        is_updating = _update_lock.locked()
        
        return templates.TemplateResponse(
            "partials/metrics.html",
            {
                "request": request,
                "ousg_supply": ousg_supply,
                "usdy_supply": usdy_supply,
                "unique_holders": unique_holders,
                "nav_deviation": nav_deviation,
                "transfer_volume": transfer_volume,
                "whale_holders": whale_holders,
                "apy_history": apy_history,
                "concentration_ratio": concentration_ratio,
                "daily_active": daily_active,
                "transfer_trend": transfer_trend,
                "holders_trend": holders_trend,
                "tvl": tvl,
                "is_updating": is_updating
            }
        )
    except Exception as e:
        return f"<div class='text-red-500'>Error loading metrics: {e}</div>"


@app.get("/api/events")
async def get_events():
    """Get Event Radar data from cache"""
    try:
        events = await cache.get_recent_events(hours=24, limit=20)
        
        # Calculate stress level
        negative_events = sum(1 for e in events if "GEO" in e.get("tags", ""))
        stress_level = calculate_stress_level(len(events), negative_events)
        
        return {
            "events": events,
            "count": len(events),
            "stress_level": stress_level
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/partials/events")
async def get_events_html(request: Request):
    """Get Event Radar data as HTML"""
    try:
        # Check if cache needs updating
        await check_and_update_cache()
        
        events = await cache.get_recent_events(hours=24, limit=20)
        
        # If no events yet, show loading message
        if not events:
            loading_html = """
            <div class="flex items-center justify-center h-96">
                <div class="text-center p-8 bg-dark-lighter rounded-lg border border-primary/30">
                    <div class="relative w-16 h-16 mx-auto mb-4">
                        <div class="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
                        <div class="absolute inset-0 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
                    </div>
                    <h3 class="text-xl font-bold text-primary mb-2">Loading Events</h3>
                    <p class="text-gray-400">Fetching latest news from GDELT</p>
                </div>
            </div>
            <script>
                setTimeout(() => {
                    window.location.reload();
                }, 10000);
            </script>
            """
            return loading_html
        
        # Calculate stress level
        negative_events = sum(1 for e in events if "GEO" in e.get("tags", ""))
        stress_level = calculate_stress_level(len(events), negative_events)
        
        return templates.TemplateResponse(
            "partials/events.html",
            {
                "request": request,
                "events": events,
                "event_count": len(events),
                "stress_level": stress_level
            }
        )
    except Exception as e:
        return f"<div class='text-red-500'>Error loading events: {e}</div>"


class SimulationRequest(BaseModel):
    scenario: str
    context: str = ""


@app.post("/api/simulate")
async def run_simulation(request: SimulationRequest):
    """Run multi-agent simulation"""
    try:
        # Load agent profiles
        with open("agents/profiles.json", "r") as f:
            all_agents = json.load(f)
        
        # Select 20 agents (all of them)
        agents = all_agents[:20]
        
        # Get current context
        context = {
            "ousg_supply": await cache.get_metric("ousg_supply") or 0,
            "usdy_supply": await cache.get_metric("usdy_supply") or 0,
            "nav_deviation": await cache.get_metric("nav_deviation") or 0,
            "events": await cache.get_recent_events(hours=24, limit=5)
        }
        
        # Add custom context
        if request.context:
            context["custom"] = request.context
        
        # Run simulation
        result = await simulation_engine.run_simulation(
            scenario=request.scenario,
            context=context,
            agents=agents
        )
        
        return result
        
    except Exception as e:
        import traceback
        print(f"❌ Simulation error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/health")
async def data_health():
    """Data health monitoring endpoint - tracks freshness and quality of all data sources"""
    try:
        return health_monitor.get_all_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/commentary")
async def market_commentary(force: bool = False):
    """AI-generated market commentary based on current metrics"""
    try:
        # Get current metrics
        ousg_supply = await cache.get_metric("ousg_supply", max_age_minutes=60) or 0
        usdy_supply = await cache.get_metric("usdy_supply", max_age_minutes=60) or 0
        holders = await cache.get_metric("unique_holders_7d", max_age_minutes=60) or 0
        events = await cache.get_recent_events(hours=24, limit=20)
        
        # Get additional context
        whale_holders = await cache.get_metric("whale_holders", max_age_minutes=60) or []
        holders_trend = await cache.get_metric("holders_trend", max_age_minutes=60) or []
        concentration_ratio = await cache.get_metric("concentration_ratio", max_age_minutes=60) or []
        apy_history = await cache.get_metric("apy_history", max_age_minutes=60) or []
        nav_deviation = await cache.get_metric("nav_deviation", max_age_minutes=60) or 0
        transfer_trend = await cache.get_metric("transfer_count_trend", max_age_minutes=60) or []
        daily_active = await cache.get_metric("daily_active_addresses", max_age_minutes=60) or []
        large_transfers = await cache.get_metric("large_transfers", max_age_minutes=60) or []
        
        # Generate commentary
        commentary = await commentary_generator.generate_commentary(
            ousg_supply=ousg_supply,
            usdy_supply=usdy_supply,
            holders=holders,
            events=events,
            whale_holders=whale_holders,
            holders_trend=holders_trend,
            concentration_ratio=concentration_ratio,
            apy_history=apy_history,
            nav_deviation=nav_deviation,
            transfer_trend=transfer_trend,
            daily_active=daily_active,
            large_transfers=large_transfers,
            force=force
        )
        
        return commentary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update")
async def trigger_manual_update():
    """Trigger manual data update"""
    
    if _update_lock.locked():
        return {"status": "already_updating", "message": "Update already in progress"}
    
    # Start update in background
    asyncio.create_task(update_all_data())
    
    return {"status": "started", "message": "Data update started"}


@app.get("/api/update/status")
async def get_update_status():
    """Get current update status and progress"""
    progress = await cache.get_update_progress()
    last_update_ts = await cache.get_metric_timestamp("ousg_supply")
    
    return {
        "is_updating": _update_lock.locked(),
        "last_update": last_update_ts.isoformat() if last_update_ts else None,
        "progress": progress
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
