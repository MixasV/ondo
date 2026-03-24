"""
AI Market Commentary Generator
Uses LLM to generate narrative summaries of market data
"""
from typing import Dict, Optional
from datetime import datetime
import json
from app.config import settings


class MarketCommentaryGenerator:
    """Generate AI-powered market commentary"""
    
    def __init__(self):
        self.last_commentary = None
        self.last_generated = None
    
    async def generate_commentary(
        self,
        ousg_supply: float,
        usdy_supply: float,
        holders: int,
        events: list,
        whale_holders: list = None,
        holders_trend: list = None,
        concentration_ratio: list = None,
        apy_history: list = None,
        nav_deviation: float = None,
        transfer_trend: list = None,
        daily_active: list = None,
        large_transfers: list = None,
        force: bool = False
    ) -> Dict:
        """Generate market commentary from current data"""
        
        # Cache for 1 hour unless forced
        if not force and self.last_commentary and self.last_generated:
            age = (datetime.utcnow() - self.last_generated).total_seconds()
            if age < 3600:
                return self.last_commentary
        
        # Prepare context
        total_supply = ousg_supply + usdy_supply
        ousg_pct = (ousg_supply / total_supply * 100) if total_supply > 0 else 0
        usdy_pct = (usdy_supply / total_supply * 100) if total_supply > 0 else 0
        
        # Count event types
        fed_events = sum(1 for e in events if "FED" in e.get("tags", []))
        reg_events = sum(1 for e in events if "REG" in e.get("tags", []))
        geo_events = sum(1 for e in events if "GEO" in e.get("tags", []))
        
        # Analyze trends
        holder_growth = None
        if holders_trend and len(holders_trend) >= 2:
            recent = holders_trend[0].get("total_holders", 0)
            week_ago = holders_trend[-1].get("total_holders", 0) if len(holders_trend) > 7 else holders_trend[-1].get("total_holders", 0)
            if week_ago > 0:
                holder_growth = ((recent - week_ago) / week_ago) * 100
        
        # Concentration analysis
        top10_concentration = None
        if concentration_ratio and len(concentration_ratio) > 0:
            top10_concentration = concentration_ratio[0].get("concentration_percent", 0)
        
        # APY analysis
        current_apy = None
        if apy_history and len(apy_history) > 0:
            current_apy = float(apy_history[0].get("apy_percent", 0))
        
        # Whale analysis
        whale_dominance = None
        if whale_holders and len(whale_holders) > 0:
            top_whale = whale_holders[0].get("balance", 0)
            whale_dominance = (top_whale / total_supply * 100) if total_supply > 0 else 0
        
        # Generate commentary using OpenRouter
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key
            )
            
            # Build detailed context with anomaly detection
            context_parts = [
                f"ONDO Finance RWA Protocol Analysis (Date: March 23, 2026):",
                f"",
                f"Current State:",
                f"- OUSG Supply: ${ousg_supply:,.0f} ({ousg_pct:.1f}% of TVL)",
                f"- USDY Supply: ${usdy_supply:,.0f} ({usdy_pct:.1f}% of TVL)",
                f"- Total TVL: ${total_supply:,.0f}",
                f"- Total Holders: {holders}",
            ]
            
            # Add NAV deviation if available
            if nav_deviation is not None:
                if nav_deviation > 0:
                    context_parts.append(f"- NAV Deviation: +{nav_deviation:.2f}% (trading at premium)")
                elif nav_deviation < 0:
                    context_parts.append(f"- NAV Deviation: {nav_deviation:.2f}% (trading at discount)")
                else:
                    context_parts.append(f"- NAV Deviation: {nav_deviation:.2f}% (at peg)")
            
            context_parts.append(f"")
            
            # Holders trend - ALL data
            if holders_trend:
                context_parts.append(f"Holders Trend ({len(holders_trend)} days):")
                for row in holders_trend[:10]:  # Show last 10 days
                    day = row.get('day', '')
                    token = row.get('token', '')
                    count = row.get('total_holders', 0)
                    context_parts.append(f"  {day}: {token} = {count} holders")
                context_parts.append(f"")
            
            # Whale holders - ALL data
            if whale_holders:
                context_parts.append(f"Whale Holders (Top 20):")
                for i, whale in enumerate(whale_holders, 1):
                    balance = whale.get('balance', 0)
                    token = whale.get('token', 'Unknown')
                    address = whale.get('holder', '')
                    label = whale.get('label')
                    entity_type = whale.get('entity_type')
                    
                    # Ensure balance is a number
                    try:
                        balance_val = float(balance) if balance else 0
                        pct = (balance_val / total_supply * 100) if total_supply > 0 else 0
                    except (ValueError, TypeError):
                        balance_val = 0
                        pct = 0
                    
                    # Format with label if available
                    if label:
                        entity_info = f" ({entity_type})" if entity_type else ""
                        context_parts.append(f"  {i}. {token}: {label}{entity_info} - ${balance_val:,.0f} ({pct:.2f}%)")
                    else:
                        context_parts.append(f"  {i}. {token}: {address[:10]}... - ${balance_val:,.0f} ({pct:.2f}%)")
                context_parts.append(f"")
            
            # Concentration ratio - ALL data
            if concentration_ratio:
                context_parts.append(f"Top 10 Concentration Ratio ({len(concentration_ratio)} days):")
                for row in concentration_ratio[:10]:  # Show last 10 days
                    day = row.get('day', '')
                    token = row.get('token', '')
                    conc = row.get('concentration_percent', 0)
                    # Ensure conc is a number
                    try:
                        conc_val = float(conc) if conc else 0
                        context_parts.append(f"  {day}: {token} = {conc_val:.1f}%")
                    except (ValueError, TypeError):
                        context_parts.append(f"  {day}: {token} = {conc}%")
                context_parts.append(f"")
            
            # APY history - ALL data
            if apy_history:
                context_parts.append(f"APY History ({len(apy_history)} days):")
                for row in apy_history[:10]:  # Show last 10 days
                    day = row.get('day', '')
                    apy = row.get('apy_percent', 0)
                    # Ensure apy is a number
                    try:
                        apy_val = float(apy) if apy else 0
                        context_parts.append(f"  {day}: {apy_val:.2f}%")
                    except (ValueError, TypeError):
                        context_parts.append(f"  {day}: {apy}%")
                context_parts.append(f"")
            
            # Transfer trend - CRITICAL for anomaly detection
            if transfer_trend:
                context_parts.append(f"Transfer Activity ({len(transfer_trend)} days):")
                for row in transfer_trend[:15]:  # Show last 15 days to catch anomalies
                    day = row.get('day', '')
                    token = row.get('token', '')
                    volume = row.get('volume', 0)
                    count = row.get('transfer_count', 0)
                    # Ensure values are numbers
                    try:
                        volume_val = float(volume) if volume else 0
                        count_val = int(count) if count else 0
                        volume_m = volume_val / 1_000_000  # Convert to millions
                        context_parts.append(f"  {day}: {token} = ${volume_m:.1f}M volume, {count_val} transfers")
                    except (ValueError, TypeError):
                        context_parts.append(f"  {day}: {token} = {volume} volume, {count} transfers")
                context_parts.append(f"")
            
            # Daily active addresses
            if daily_active:
                context_parts.append(f"Daily Active Addresses ({len(daily_active)} days):")
                for row in daily_active[:10]:  # Show last 10 days
                    day = row.get('day', '')
                    token = row.get('token', '')
                    active = row.get('active_addresses', 0)
                    try:
                        active_val = int(active) if active else 0
                        context_parts.append(f"  {day}: {token} = {active_val} active addresses")
                    except (ValueError, TypeError):
                        context_parts.append(f"  {day}: {token} = {active} active addresses")
                context_parts.append(f"")
            
            # Market events
            context_parts.extend([
                f"Market Events (24h):",
                f"- Federal Reserve: {fed_events} events",
                f"- Regulatory: {reg_events} events",
                f"- Geopolitical: {geo_events} events",
            ])
            
            # Add event titles for context
            if events:
                context_parts.append(f"")
                context_parts.append(f"Recent Headlines:")
                for event in events[:5]:
                    context_parts.append(f"- {event.get('title', '')[:100]}")
            
            # Large transfers - CRITICAL for anomaly detection
            if large_transfers:
                # Group by day and find anomalous days
                from collections import defaultdict
                daily_volumes = defaultdict(lambda: {'volume': 0, 'transfers': []})
                
                for transfer in large_transfers:
                    day = transfer.get('day', '')[:10]  # Get date only
                    amount = float(transfer.get('amount', 0))
                    daily_volumes[day]['volume'] += amount
                    daily_volumes[day]['transfers'].append(transfer)
                
                # Calculate average daily volume for context
                all_volumes = [data['volume'] for data in daily_volumes.values()]
                avg_volume = sum(all_volumes) / len(all_volumes) if all_volumes else 0
                
                # Find top 3 days by volume
                top_days = sorted(daily_volumes.items(), key=lambda x: x[1]['volume'], reverse=True)[:3]
                
                if top_days:
                    context_parts.append(f"")
                    context_parts.append(f"🚨 LARGE TRANSFER ANOMALIES (>$100K, last 30 days):")
                    context_parts.append(f"Average daily volume: ${avg_volume/1e6:.1f}M")
                    context_parts.append(f"")
                    
                    for day, data in top_days:
                        volume_m = data['volume'] / 1_000_000
                        count = len(data['transfers'])
                        deviation = ((data['volume'] - avg_volume) / avg_volume * 100) if avg_volume > 0 else 0
                        
                        context_parts.append(f"📅 {day}: ${volume_m:.1f}M in {count} large transfers ({deviation:+.0f}% vs avg)")
                        
                        # Show top 3 transfers for this day with analysis
                        top_transfers = sorted(data['transfers'], key=lambda x: float(x.get('amount', 0)), reverse=True)[:3]
                        for t in top_transfers:
                            amount_m = float(t.get('amount', 0)) / 1_000_000
                            from_addr = t.get('from_address', '')
                            to_addr = t.get('to_address', '')
                            from_label = t.get('from_label', from_addr[:10] + '...')
                            to_label = t.get('to_label', to_addr[:10] + '...')
                            token = t.get('token', '')
                            
                            # Identify transfer type
                            transfer_type = ""
                            if from_addr.startswith('0x0000000000'):
                                transfer_type = " [MINT]"
                            elif to_addr.startswith('0x0000000000'):
                                transfer_type = " [BURN]"
                            elif from_label == to_label:
                                transfer_type = " [INTERNAL]"
                            
                            context_parts.append(f"    • {token}: ${amount_m:.1f}M from {from_label} → {to_label}{transfer_type}")
                    
                    context_parts.append(f"")
                    context_parts.append(f"⚠️  ANALYSIS REQUIRED: Explain what these large transfers mean for protocol health, liquidity, and risk.")
                    context_parts.append(f"")
            
            context = "\n".join(context_parts)
            
            prompt = f"""You are a senior DeFi analyst specializing in Real-World Asset (RWA) tokenization. Today is March 23, 2026. Analyze the following CURRENT data and provide a professional market commentary.

{context}

OUTPUT FORMAT (MANDATORY):

Your response MUST be written in ENGLISH ONLY and follow this exact structure:

ANOMALIES:
[List 2-4 specific anomalies found in the data. Each anomaly should be one line starting with "•" and include specific numbers and dates. Focus on: unusual volume spikes, concentration changes, whale movements, transfer patterns that deviate from normal.]

ANALYSIS:
[Write 2-3 short paragraphs explaining what these anomalies mean. Include:
- WHY the anomalies are significant
- WHO is involved (mint/burn, whales, exchanges)
- WHAT risks they create
- HOW they connect to market events]

RECOMMENDATIONS:
[List 2-3 specific monitoring recommendations. Each should start with "•" and be actionable, e.g., "Monitor address 0xabc... for movements >$50M"]

CRITICAL RULES:
1. WRITE IN ENGLISH ONLY - ignore any non-English text in the data
2. Use ONLY data provided above - do NOT make up numbers
3. Calculate deviations (e.g., "March 9 was 300% above average")
4. Identify transfer types: [MINT], [BURN], whale-to-whale
5. Be SPECIFIC with addresses, dates, and amounts
6. Explain implications, not just describe data

Now provide your analysis IN ENGLISH:"""

            response = await client.chat.completions.create(
                model="google/gemini-3-flash-preview",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            # stepfun returns both reasoning and content
            # Use content if available, otherwise fall back to reasoning
            message = response.choices[0].message
            commentary_text = message.content if message.content else (message.reasoning if hasattr(message, 'reasoning') else None)
            
            if not commentary_text:
                raise Exception("Empty response from LLM")
            
            # Clean up the text
            commentary_text = commentary_text.strip()
            
            # Remove markdown formatting
            commentary_text = commentary_text.replace('**', '')  # Remove bold
            commentary_text = commentary_text.replace('*', '')   # Remove italic
            commentary_text = commentary_text.replace('###', '') # Remove headers
            commentary_text = commentary_text.replace('##', '')
            commentary_text = commentary_text.replace('#', '')
            
            # Ensure proper paragraph spacing
            # Replace multiple newlines with double newline
            import re
            commentary_text = re.sub(r'\n{3,}', '\n\n', commentary_text)
            
            self.last_commentary = {
                "text": commentary_text,
                "generated_at": datetime.utcnow().isoformat(),
                "metrics": {
                    "ousg_supply": ousg_supply,
                    "usdy_supply": usdy_supply,
                    "holders": holders,
                    "holder_growth": holder_growth,
                    "top10_concentration": top10_concentration,
                    "current_apy": current_apy,
                    "whale_dominance": whale_dominance,
                    "fed_events": fed_events,
                    "reg_events": reg_events,
                    "geo_events": geo_events
                }
            }
            self.last_generated = datetime.utcnow()
            
            return self.last_commentary
            
        except Exception as e:
            print(f"⚠️  LLM commentary failed: {e}")
            # Fallback to rule-based commentary
            return self._generate_fallback_commentary(
                ousg_supply, usdy_supply, holders, 
                fed_events, reg_events, geo_events,
                holder_growth, top10_concentration, current_apy, whale_dominance
            )
    
    def _generate_fallback_commentary(
        self,
        ousg_supply: float,
        usdy_supply: float,
        holders: int,
        fed_events: int,
        reg_events: int,
        geo_events: int,
        holder_growth: float = None,
        top10_concentration: float = None,
        current_apy: float = None,
        whale_dominance: float = None
    ) -> Dict:
        """Generate rule-based commentary when LLM unavailable"""
        
        total = ousg_supply + usdy_supply
        usdy_pct = (usdy_supply / total * 100) if total > 0 else 0
        
        # Build commentary
        parts = []
        
        # Supply and concentration analysis
        if usdy_supply > ousg_supply * 100:
            parts.append(f"USDY dominates at {usdy_pct:.1f}% of ${total/1e6:.1f}M TVL, reflecting strong retail demand for tokenized T-bills.")
            
            if current_apy:
                parts.append(f"Current {current_apy:.2f}% APY provides competitive yield vs traditional stablecoins.")
            
            if top10_concentration and top10_concentration > 80:
                parts.append(f"However, top 10 holders control {top10_concentration:.0f}% of supply, indicating concentration risk.")
            elif whale_dominance and whale_dominance > 30:
                parts.append(f"Largest holder controls {whale_dominance:.1f}% of supply, suggesting whale concentration risk.")
        
        # Holder growth analysis
        if holder_growth is not None:
            if holder_growth > 10:
                parts.append(f"Strong holder growth of {holder_growth:+.1f}% signals increasing adoption.")
            elif holder_growth < -10:
                parts.append(f"Declining holders ({holder_growth:.1f}%) may indicate reduced confidence or profit-taking.")
        
        # Event analysis with macro context
        if fed_events > 3:
            parts.append(f"High Fed activity ({fed_events} events) may pressure treasury yields, impacting RWA returns.")
        elif reg_events > 3:
            parts.append(f"Regulatory scrutiny ({reg_events} events) could affect tokenized securities compliance requirements.")
        elif geo_events > 2:
            parts.append(f"Geopolitical tensions ({geo_events} events) may drive flight to stable, yield-bearing assets.")
        
        # Ensure we have at least 2 sentences
        if len(parts) < 2:
            parts.append(f"Protocol maintains {holders} active holders with healthy distribution across OUSG and USDY tokens.")
        
        commentary_text = " ".join(parts)
        
        return {
            "text": commentary_text,
            "generated_at": datetime.utcnow().isoformat(),
            "metrics": {
                "ousg_supply": ousg_supply,
                "usdy_supply": usdy_supply,
                "holders": holders,
                "holder_growth": holder_growth,
                "top10_concentration": top10_concentration,
                "current_apy": current_apy,
                "whale_dominance": whale_dominance,
                "fed_events": fed_events,
                "reg_events": reg_events,
                "geo_events": geo_events
            },
            "fallback": True
        }


# Global instance
commentary_generator = MarketCommentaryGenerator()
