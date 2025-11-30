"""
Enhanced AI Trading Agent
Implements best practices for reliable AI-assisted trading decisions
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass
import anthropic

logger = logging.getLogger(__name__)


@dataclass
class AIConsensus:
    """Result from multi-agent consensus"""
    direction: str
    confidence: float
    agreement_level: float  # 0-1, how much agents agreed
    entry: float
    stop: float
    target: float
    reasoning: str
    dissenting_views: List[str]


class EnhancedTradingAgent:
    """
    Enhanced AI agent with:
    1. Structured prompts with examples
    2. Multi-perspective analysis
    3. Self-verification loop
    4. Constrained JSON output
    5. Performance-aware context
    """

    def __init__(self, api_key: str, config: Dict[str, Any] = None):
        """Initialize enhanced agent"""
        self.client = anthropic.Anthropic(api_key=api_key)
        self.config = config or {}
        self.model = config.get('claude', {}).get('model', 'claude-sonnet-4-5-20250929')

        # Track AI performance for context
        self.recent_decisions: List[Dict] = []
        self.performance_stats = {
            'total_signals': 0,
            'wins': 0,
            'losses': 0,
            'last_5_results': []
        }

        logger.info(f"EnhancedTradingAgent initialized with model: {self.model}")

    def _get_system_prompt(self) -> str:
        """
        Structured system prompt with clear rules and examples
        """
        return """You are a professional NQ futures trader analyzing Fair Value Gaps (FVGs).

## YOUR ROLE
You analyze market data and decide whether to take a trade. You must be SELECTIVE - most of the time, the answer should be NO TRADE.

## STRICT RULES (NEVER VIOLATE)
1. Minimum Risk/Reward: 3:1 (if R/R < 3, output NO_TRADE)
2. Stop Loss Range: 15-50 points (never outside this range)
3. Trade WITH trend only (LONG when EMAs bullish, SHORT when bearish)
4. Entry must be AT or NEAR an FVG zone (within 20 points)
5. If unsure, output NO_TRADE (patience is profitable)

## FVG TRADING LOGIC
- BEARISH FVG (gap down) = potential LONG zone (price may bounce up from it)
- BULLISH FVG (gap up) = potential SHORT zone (price may reject down from it)
- Wait for price to REACH the zone before entering

## OUTPUT FORMAT (JSON ONLY)
You must respond with ONLY valid JSON, no other text:

{
  "analysis": {
    "trend": "BULLISH|BEARISH|NEUTRAL",
    "trend_strength": "STRONG|MODERATE|WEAK",
    "nearest_long_zone": {"price": 0, "distance": 0, "quality": "HIGH|MEDIUM|LOW"},
    "nearest_short_zone": {"price": 0, "distance": 0, "quality": "HIGH|MEDIUM|LOW"}
  },
  "decision": "LONG|SHORT|NO_TRADE",
  "trade_details": {
    "entry": 0,
    "stop": 0,
    "target": 0,
    "risk_points": 0,
    "reward_points": 0,
    "risk_reward": 0.0
  },
  "confidence": 0.0,
  "reasoning": "One sentence explanation",
  "wait_for": "What price action would trigger entry (if NO_TRADE)"
}

## EXAMPLES

### Example 1: Good LONG Setup
Market: Price at 21000, Bearish FVG at 20950-20960, EMAs bullish (21>75>150)
Output:
{
  "analysis": {"trend": "BULLISH", "trend_strength": "STRONG", "nearest_long_zone": {"price": 20955, "distance": 45, "quality": "HIGH"}, "nearest_short_zone": {"price": 21100, "distance": 100, "quality": "LOW"}},
  "decision": "NO_TRADE",
  "trade_details": {"entry": 0, "stop": 0, "target": 0, "risk_points": 0, "reward_points": 0, "risk_reward": 0},
  "confidence": 0,
  "reasoning": "Good setup but price not at zone yet - 45 points away",
  "wait_for": "Price to pull back to 20950-20960 bearish FVG zone"
}

### Example 2: Taking a Trade
Market: Price at 20958 (inside bearish FVG 20950-20960), EMAs bullish, rejection wick forming
Output:
{
  "analysis": {"trend": "BULLISH", "trend_strength": "STRONG", "nearest_long_zone": {"price": 20955, "distance": 3, "quality": "HIGH"}, "nearest_short_zone": {"price": 21100, "distance": 142, "quality": "LOW"}},
  "decision": "LONG",
  "trade_details": {"entry": 20958, "stop": 20925, "target": 21057, "risk_points": 33, "reward_points": 99, "risk_reward": 3.0},
  "confidence": 0.75,
  "reasoning": "Price at high-quality bearish FVG with bullish trend, 3:1 R/R achieved",
  "wait_for": null
}

### Example 3: Rejecting Bad Setup
Market: Price at 21050, nearest FVG at 20900 (150 points away), EMAs mixed
Output:
{
  "analysis": {"trend": "NEUTRAL", "trend_strength": "WEAK", "nearest_long_zone": {"price": 20900, "distance": 150, "quality": "MEDIUM"}, "nearest_short_zone": {"price": 21200, "distance": 150, "quality": "MEDIUM"}},
  "decision": "NO_TRADE",
  "trade_details": {"entry": 0, "stop": 0, "target": 0, "risk_points": 0, "reward_points": 0, "risk_reward": 0},
  "confidence": 0,
  "reasoning": "No trade - price far from any FVG zone and trend unclear",
  "wait_for": "Clear trend development and price approaching an FVG"
}

Remember: Professional traders wait for setups. NO_TRADE is often the best decision."""

    def _build_market_context(
        self,
        current_price: float,
        fvg_context: Dict[str, Any],
        market_data: Dict[str, float],
        recent_performance: str = ""
    ) -> str:
        """Build structured market context for the AI"""

        # Format FVG information
        bearish_fvg = fvg_context.get('nearest_bearish_fvg', {})
        bullish_fvg = fvg_context.get('nearest_bullish_fvg', {})

        context = f"""## CURRENT MARKET STATE

**Price**: {current_price:.2f}

**Trend Indicators**:
- EMA 21: {market_data.get('ema21', 0):.2f}
- EMA 75: {market_data.get('ema75', 0):.2f}
- EMA 150: {market_data.get('ema150', 0):.2f}
- Stochastic %D: {market_data.get('stochastic', 50):.1f}

**Nearest Bearish FVG (potential LONG zone)**:
- Zone: {bearish_fvg.get('bottom', 'None'):.2f} - {bearish_fvg.get('top', 'None'):.2f}
- Distance: {bearish_fvg.get('distance', 'N/A')} points
- Size: {bearish_fvg.get('size', 0):.1f} points
- Age: {bearish_fvg.get('age_bars', 0)} bars

**Nearest Bullish FVG (potential SHORT zone)**:
- Zone: {bullish_fvg.get('bottom', 'None'):.2f} - {bullish_fvg.get('top', 'None'):.2f}
- Distance: {bullish_fvg.get('distance', 'N/A')} points
- Size: {bullish_fvg.get('size', 0):.1f} points
- Age: {bullish_fvg.get('age_bars', 0)} bars
"""

        if recent_performance:
            context += f"\n**Recent Performance**:\n{recent_performance}\n"

        context += "\nAnalyze this setup and provide your decision in JSON format."

        return context

    def analyze_setup(
        self,
        current_price: float,
        fvg_context: Dict[str, Any],
        market_data: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Main analysis with structured prompting
        """
        # Build performance context
        perf_context = ""
        if self.performance_stats['total_signals'] > 0:
            win_rate = self.performance_stats['wins'] / self.performance_stats['total_signals']
            perf_context = f"Last 5 trades: {self.performance_stats['last_5_results']}, Win rate: {win_rate:.1%}"

        # Build context
        market_context = self._build_market_context(
            current_price, fvg_context, market_data, perf_context
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.1,  # Low temperature for consistency
                system=self._get_system_prompt(),
                messages=[{"role": "user", "content": market_context}]
            )

            # Parse JSON response
            response_text = response.content[0].text.strip()

            # Clean up response (remove markdown code blocks if present)
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()

            decision = json.loads(response_text)

            logger.info(f"AI Decision: {decision.get('decision')} (confidence: {decision.get('confidence')})")

            return {
                'success': True,
                'decision': decision,
                'raw_response': response_text
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return {
                'success': False,
                'error': f"JSON parse error: {e}",
                'raw_response': response_text if 'response_text' in locals() else None
            }
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_second_opinion(
        self,
        current_price: float,
        fvg_context: Dict[str, Any],
        market_data: Dict[str, float],
        first_decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get a second opinion by asking AI to critique its own decision
        """
        critique_prompt = f"""You made this trading decision:

Decision: {first_decision.get('decision')}
Entry: {first_decision.get('trade_details', {}).get('entry')}
Stop: {first_decision.get('trade_details', {}).get('stop')}
Target: {first_decision.get('trade_details', {}).get('target')}
Reasoning: {first_decision.get('reasoning')}

Now critically evaluate this decision:
1. What could go wrong?
2. Is the stop loss placement logical?
3. Is the target realistic given current volatility?
4. Would you still take this trade? Why or why not?

Respond with JSON:
{{
  "critique": "Your honest critique",
  "risks_identified": ["risk1", "risk2"],
  "still_valid": true/false,
  "adjusted_confidence": 0.0-1.0,
  "recommendation": "PROCEED|REDUCE_SIZE|SKIP"
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": critique_prompt}]
            )

            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            critique = json.loads(response_text.strip())

            logger.info(f"Self-critique: {critique.get('recommendation')} (adjusted confidence: {critique.get('adjusted_confidence')})")

            return {
                'success': True,
                'critique': critique
            }

        except Exception as e:
            logger.error(f"Self-critique failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_multi_perspective_analysis(
        self,
        current_price: float,
        fvg_context: Dict[str, Any],
        market_data: Dict[str, float]
    ) -> AIConsensus:
        """
        Get analysis from multiple "perspectives" and find consensus

        Perspectives:
        1. Trend Follower - Only trades with trend
        2. Mean Reversion - Looks for reversals at extremes
        3. Risk Manager - Focuses on R/R and position sizing
        """
        perspectives = []

        # Perspective 1: Trend Follower
        trend_prompt = f"""You are a TREND FOLLOWING trader. You ONLY trade in the direction of the trend.

Current Price: {current_price}
EMA21: {market_data.get('ema21', 0):.2f}
EMA75: {market_data.get('ema75', 0):.2f}
EMA150: {market_data.get('ema150', 0):.2f}

Question: Based ONLY on trend, should we be looking for LONG, SHORT, or NO_TRADE?
Respond with JSON: {{"direction": "LONG|SHORT|NO_TRADE", "reason": "brief explanation"}}"""

        # Perspective 2: Zone Trader
        zone_prompt = f"""You are an FVG ZONE trader. You only care about price at zones.

Current Price: {current_price}
Nearest Bearish FVG (LONG zone): {fvg_context.get('nearest_bearish_fvg', {})}
Nearest Bullish FVG (SHORT zone): {fvg_context.get('nearest_bullish_fvg', {})}

Question: Is price at a tradeable zone right now?
Respond with JSON: {{"at_zone": true/false, "zone_type": "LONG|SHORT|NONE", "reason": "brief explanation"}}"""

        # Perspective 3: Risk Manager
        risk_prompt = f"""You are a RISK MANAGER. You evaluate if a trade setup has acceptable risk.

For a LONG at {current_price}:
- Logical stop: below the FVG at ~{fvg_context.get('nearest_bearish_fvg', {}).get('bottom', 0) - 10:.0f}
- Potential target: recent high or next resistance

For a SHORT at {current_price}:
- Logical stop: above the FVG at ~{fvg_context.get('nearest_bullish_fvg', {}).get('top', 0) + 10:.0f}
- Potential target: recent low or next support

Question: Can we achieve 3:1 R/R with reasonable stop placement?
Respond with JSON: {{"acceptable_risk": true/false, "best_direction": "LONG|SHORT|NONE", "reason": "brief explanation"}}"""

        try:
            # Get all perspectives
            for prompt in [trend_prompt, zone_prompt, risk_prompt]:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=200,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text.strip()
                if text.startswith("```"):
                    text = text.split("```")[1].replace("json", "").strip()
                perspectives.append(json.loads(text))

            # Analyze consensus
            trend_view = perspectives[0]
            zone_view = perspectives[1]
            risk_view = perspectives[2]

            # Count votes
            votes = {'LONG': 0, 'SHORT': 0, 'NO_TRADE': 0}

            if trend_view.get('direction') in votes:
                votes[trend_view['direction']] += 1
            else:
                votes['NO_TRADE'] += 1

            if zone_view.get('at_zone') and zone_view.get('zone_type') in ['LONG', 'SHORT']:
                votes[zone_view['zone_type']] += 1
            else:
                votes['NO_TRADE'] += 1

            if risk_view.get('acceptable_risk') and risk_view.get('best_direction') in ['LONG', 'SHORT']:
                votes[risk_view['best_direction']] += 1
            else:
                votes['NO_TRADE'] += 1

            # Determine consensus
            max_votes = max(votes.values())
            consensus_direction = [k for k, v in votes.items() if v == max_votes][0]
            agreement = max_votes / 3.0

            # If no strong consensus, default to NO_TRADE
            if agreement < 0.67 or consensus_direction == 'NO_TRADE':
                consensus_direction = 'NO_TRADE'

            # Collect dissenting views
            dissenting = []
            if trend_view.get('direction') != consensus_direction:
                dissenting.append(f"Trend: {trend_view.get('reason')}")
            if zone_view.get('zone_type') != consensus_direction:
                dissenting.append(f"Zone: {zone_view.get('reason')}")
            if risk_view.get('best_direction') != consensus_direction:
                dissenting.append(f"Risk: {risk_view.get('reason')}")

            logger.info(f"Multi-perspective consensus: {consensus_direction} (agreement: {agreement:.0%})")

            return AIConsensus(
                direction=consensus_direction,
                confidence=agreement * 0.8,  # Cap confidence based on agreement
                agreement_level=agreement,
                entry=current_price if consensus_direction != 'NO_TRADE' else 0,
                stop=0,  # Would need full analysis to set
                target=0,
                reasoning=f"Consensus from trend/zone/risk analysis",
                dissenting_views=dissenting
            )

        except Exception as e:
            logger.error(f"Multi-perspective analysis failed: {e}")
            return AIConsensus(
                direction='NO_TRADE',
                confidence=0,
                agreement_level=0,
                entry=0, stop=0, target=0,
                reasoning=f"Analysis failed: {e}",
                dissenting_views=[]
            )

    def record_outcome(self, decision: str, result: str):
        """Record trade outcome for learning"""
        self.performance_stats['total_signals'] += 1
        if result == 'WIN':
            self.performance_stats['wins'] += 1
        else:
            self.performance_stats['losses'] += 1

        self.performance_stats['last_5_results'].append(result)
        if len(self.performance_stats['last_5_results']) > 5:
            self.performance_stats['last_5_results'].pop(0)

    def get_performance_summary(self) -> str:
        """Get AI performance summary"""
        total = self.performance_stats['total_signals']
        if total == 0:
            return "No trades recorded yet"

        win_rate = self.performance_stats['wins'] / total
        return f"AI Performance: {self.performance_stats['wins']}/{total} wins ({win_rate:.1%}), Last 5: {self.performance_stats['last_5_results']}"
