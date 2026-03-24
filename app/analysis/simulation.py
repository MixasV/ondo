import asyncio
import json
from typing import List, Dict
from openai import AsyncOpenAI
from app.config import settings


class MultiAgentSimulation:
    """Multi-agent simulation engine using LLM"""
    
    def __init__(self, api_key: str = None):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key or settings.openrouter_api_key
        )
        self.model = "nvidia/nemotron-3-super-120b-a12b:free"
    
    async def run_simulation(
        self,
        scenario: str,
        context: Dict,
        agents: List[Dict]
    ) -> Dict:
        """
        Run multi-agent simulation
        
        Args:
            scenario: User-provided scenario description
            context: Current market data (metrics, events)
            agents: List of agent profiles
        
        Returns:
            Simulation results with consensus and forecast
        """
        
        # Round 1: Independent agent responses
        # Group agents by model to parallelize requests per model
        agents_by_model = {}
        for agent in agents:
            model = agent.get("model", self.model)
            if model not in agents_by_model:
                agents_by_model[model] = []
            agents_by_model[model].append(agent)
        
        round1_responses = []
        for model, model_agents in agents_by_model.items():
            print(f"  Round 1: Processing {len(model_agents)} agents with {model}")
            # Process agents of same model in parallel
            tasks = [self._agent_response(agent, scenario, context, round_num=1) for agent in model_agents]
            responses = await asyncio.gather(*tasks)
            round1_responses.extend(responses)
            await asyncio.sleep(3)  # Increased delay between model groups to avoid rate limits
        
        # Round 2: Interaction round (agents see each other's responses)
        round2_context = {
            **context,
            "round1_responses": round1_responses
        }
        
        round2_responses = []
        for model, model_agents in agents_by_model.items():
            print(f"  Round 2: Processing {len(model_agents)} agents with {model}")
            # Process agents of same model in parallel
            tasks = [self._agent_response(agent, scenario, round2_context, round_num=2) for agent in model_agents]
            responses = await asyncio.gather(*tasks)
            round2_responses.extend(responses)
            await asyncio.sleep(3)  # Increased delay between model groups to avoid rate limits
        
        # Aggregation: Synthesize consensus
        consensus = await self._synthesize_consensus(
            scenario,
            context,
            round1_responses,
            round2_responses
        )
        
        return {
            "scenario": scenario,
            "agents_count": len(agents),
            "rounds": 2,
            "model": self.model,
            "round1": round1_responses,
            "round2": round2_responses,
            "consensus": consensus
        }
    
    async def _agent_response(
        self,
        agent: Dict,
        scenario: str,
        context: Dict,
        round_num: int
    ) -> Dict:
        """Get single agent's response to scenario"""
        
        prompt = self._build_agent_prompt(agent, scenario, context, round_num)
        
        # Use agent-specific model if specified, otherwise use default
        model = agent.get("model", self.model)
        max_tokens = 2500
        
        # Retry logic for rate limits
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": agent["system_prompt"]},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=max_tokens
                )
                
                # Handle different response formats (content vs reasoning)
                message = response.choices[0].message
                content = message.content if message.content else (message.reasoning if hasattr(message, 'reasoning') else None)
                
                if not content:
                    raise Exception(f"Empty response from {model}")
                
                # Parse response (expecting JSON format)
                try:
                    parsed = json.loads(content)
                except:
                    # Fallback if not JSON
                    parsed = {
                        "action": "HOLD",
                        "reasoning": content[:500],  # Truncate if too long
                        "confidence": 50
                    }
                
                return {
                    "agent_name": agent["name"],
                    "agent_type": agent["type"],
                    "agent_model": model,
                    "round": round_num,
                    **parsed
                }
            
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a rate limit error
                if "429" in error_str or "rate limit" in error_str.lower():
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        print(f"⚠️  Rate limit for {agent['name']}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"⚠️  Rate limit exceeded for {agent['name']} after {max_retries} attempts")
                else:
                    print(f"⚠️  Agent {agent['name']} error: {e}")
                
                # Return fallback response
                return {
                    "agent_name": agent["name"],
                    "agent_type": agent["type"],
                    "agent_model": model,
                    "round": round_num,
                    "action": "HOLD",
                    "reasoning": f"Error: {str(e)[:100]}",
                    "confidence": 0
                }
    
    def _build_agent_prompt(
        self,
        agent: Dict,
        scenario: str,
        context: Dict,
        round_num: int
    ) -> str:
        """Build prompt for agent"""
        
        base_prompt = f"""
SCENARIO: {scenario}

CURRENT MARKET DATA:
- OUSG Supply: {context.get('ousg_supply', 'N/A')}
- USDY Supply: {context.get('usdy_supply', 'N/A')}
- NAV Deviation: {context.get('nav_deviation', 'N/A')}%
- Recent Events: {len(context.get('events', []))} in last 24h

YOUR PROFILE:
{agent.get('description', '')}

"""
        
        # Add custom context if provided
        if context.get('custom'):
            base_prompt += f"\nADDITIONAL CONTEXT:\n{context['custom']}\n\n"
        
        if round_num == 2 and 'round1_responses' in context:
            # Show diverse responses from different models/perspectives
            responses = context['round1_responses']
            
            # Try to get mix of different models
            agent_model = agent.get('model', self.model)
            same_model = [r for r in responses if r.get('agent_model') == agent_model]
            other_models = [r for r in responses if r.get('agent_model') != agent_model]
            
            # Show 2 from same model + 3 from other models if available
            selected = same_model[:2] + other_models[:3]
            if len(selected) < 5:
                # Fill up to 5 with any remaining
                selected = responses[:5]
            
            base_prompt += "\nOTHER AGENTS' INITIAL REACTIONS:\n"
            for resp in selected:
                reasoning = resp.get('reasoning', '') or ''
                base_prompt += f"- {resp['agent_name']}: {resp['action']} ({reasoning[:100]}...)\n"
        
        base_prompt += """
Respond in JSON format:
{
    "action": "BUY" | "HOLD" | "SELL",
    "reasoning": "your analysis in 1-2 sentences",
    "confidence": 0-100
}
"""
        
        return base_prompt
    
    async def _synthesize_consensus(
        self,
        scenario: str,
        context: Dict,
        round1: List[Dict],
        round2: List[Dict]
    ) -> Dict:
        """Synthesize all agent responses into consensus forecast"""
        
        # Count actions
        actions = {"BUY": 0, "HOLD": 0, "SELL": 0}
        for resp in round2:
            action = resp.get("action", "HOLD")
            actions[action] = actions.get(action, 0) + 1
        
        total = sum(actions.values())
        
        # Calculate consensus
        consensus_action = max(actions, key=actions.get)
        consensus_strength = (actions[consensus_action] / total * 100) if total > 0 else 0
        
        # Build forecast prompt
        prompt = f"""
Analyze this multi-agent simulation and provide a forecast.

SCENARIO: {scenario}

AGENT CONSENSUS:
- BUY: {actions['BUY']} agents ({actions['BUY']/total*100:.0f}%)
- HOLD: {actions['HOLD']} agents ({actions['HOLD']/total*100:.0f}%)
- SELL: {actions['SELL']} agents ({actions['SELL']/total*100:.0f}%)

Provide forecast in JSON:
{{
    "ousg_supply_change": "↑ X-Y% (30d)" or "↓ X-Y% (30d)",
    "usdy_supply_change": "↑ X-Y% (30d)" or "↓ X-Y% (30d)",
    "nav_deviation_forecast": "brief description",
    "risk_level": "LOW" | "MEDIUM" | "HIGH",
    "confidence": 0-100,
    "summary": "2-3 sentence summary"
}}
"""
        
        # Retry logic for rate limits
        max_retries = 3
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=2500
                )
                
                # Handle different response formats
                message = response.choices[0].message
                content = message.content if message.content else (message.reasoning if hasattr(message, 'reasoning') else None)
                
                if not content:
                    raise Exception("Empty forecast response from LLM")
                
                forecast = json.loads(content)
                
                return {
                    "action_distribution": actions,
                    "consensus_action": consensus_action,
                    "consensus_strength": round(consensus_strength, 1),
                    "forecast": forecast
                }
                
            except json.JSONDecodeError as e:
                print(f"⚠️  Forecast JSON parse error: {e}")
                print(f"⚠️  Raw content: {content[:200]}")
                
                # Return fallback forecast
                return {
                    "action_distribution": actions,
                    "consensus_action": consensus_action,
                    "consensus_strength": round(consensus_strength, 1),
                    "forecast": {
                        "ousg_supply_change": "Unable to forecast",
                        "usdy_supply_change": "Unable to forecast",
                        "nav_deviation_forecast": "Unable to forecast",
                        "risk_level": "MEDIUM",
                        "confidence": 0,
                        "summary": f"Consensus: {consensus_action} ({consensus_strength:.0f}% agreement)"
                    }
                }
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a rate limit error
                if "429" in error_str or "rate limit" in error_str.lower():
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        print(f"⚠️  Rate limit in consensus, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"⚠️  Rate limit exceeded in consensus after {max_retries} attempts")
                else:
                    print(f"⚠️  Forecast generation error: {e}")
                
                # Return fallback forecast
                return {
                    "action_distribution": actions,
                    "consensus_action": consensus_action,
                    "consensus_strength": round(consensus_strength, 1),
                    "forecast": {
                        "ousg_supply_change": "Unable to forecast",
                        "usdy_supply_change": "Unable to forecast",
                        "nav_deviation_forecast": "Unable to forecast",
                        "risk_level": "MEDIUM",
                        "confidence": 0,
                        "summary": f"Consensus: {consensus_action} ({consensus_strength:.0f}% agreement). Error: {str(e)[:100]}"
                    }
                }


simulation_engine = MultiAgentSimulation()
