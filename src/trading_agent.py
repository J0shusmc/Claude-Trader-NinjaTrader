"""
Claude Trading Agent Module
Main reasoning engine for NQ trading decisions
"""

import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import os
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class TradingAgent:
    """Claude-powered trading decision engine"""

    def __init__(self, config: Dict[str, Any], api_key: Optional[str] = None):
        """
        Initialize Trading Agent

        Args:
            config: Configuration dictionary with trading parameters
            api_key: Anthropic API key (or from environment)
        """
        self.config = config
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')

        if not self.api_key:
            raise ValueError("Anthropic API key required (set ANTHROPIC_API_KEY or pass api_key)")

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-5-20250929"

        # Extract config parameters
        self.min_risk_reward = config.get('trading_params', {}).get('min_risk_reward', 3.0)
        self.confidence_threshold = config.get('trading_params', {}).get('confidence_threshold', 0.65)
        self.stop_loss_min = config.get('risk_management', {}).get('stop_loss_min', 15)
        self.stop_loss_default = config.get('risk_management', {}).get('stop_loss_default', 20)
        self.stop_loss_max = config.get('risk_management', {}).get('stop_loss_max', 50)
        self.stop_buffer = config.get('risk_management', {}).get('stop_buffer', 5)

        logger.info(f"TradingAgent initialized (model={self.model}, min_rr={self.min_risk_reward})")

    def build_prompt(
        self,
        fvg_context: Dict[str, Any],
        market_data: Dict[str, Any],
        memory_context: Optional[Dict[str, Any]] = None,
        previous_analysis: Optional[str] = None
    ) -> str:
        """
        Build Claude prompt for trade analysis

        Args:
            fvg_context: FVG market context
            market_data: Market indicators (EMA, Stochastic, etc.)
            memory_context: Past trade performance data
            previous_analysis: Previous analysis state (formatted string)

        Returns:
            Formatted prompt string
        """
        prompt = f"""You are an expert NQ futures trader specializing in price action analysis using Fair Value Gaps, EMAs, and momentum indicators.

YOUR TRADING PHILOSOPHY:
========================
- PATIENCE IS KEY: It's perfectly acceptable to wait for quality setups
- Don't force trades - wait for confluence and proper setup development
- Maintain continuity in your analysis across bars
- Update your assessment incrementally based on what changed
- Track setups over multiple bars as they develop

"""

        # Add previous analysis if available
        if previous_analysis:
            prompt += previous_analysis + "\n"
            prompt += """
CRITICAL INSTRUCTIONS FOR INCREMENTAL ANALYSIS:
===============================================
You are NOT doing a fresh analysis. You are UPDATING your previous assessment.

Ask yourself:
1. What changed with this new bar?
2. Is my previous setup still valid?
3. Should I continue waiting or has the setup improved/deteriorated?
4. Has price moved closer to or further from my planned entry?

If you were waiting for a setup and nothing meaningful changed:
- Keep the same assessment
- Increment setup_age_bars
- Update only what's relevant (e.g., distance to entry)

If you identified no setup previously and still see no setup:
- It's OKAY to stay in "none" status
- Explain why you're still waiting
- Don't force a trade just because time has passed

"""

        prompt += f"""
CURRENT MARKET CONTEXT (NEW BAR):
==================================

Price: {fvg_context['current_price']:.2f}

FAIR VALUE GAPS:
"""

        # Add bullish FVG info
        if fvg_context.get('nearest_bullish_fvg'):
            fvg = fvg_context['nearest_bullish_fvg']
            prompt += f"""
Nearest Bullish FVG (SHORT opportunity):
  Zone: {fvg['bottom']:.2f} - {fvg['top']:.2f}
  Size: {fvg['size']:.2f} points
  Distance: {fvg['distance']:+.2f} points
  Age: {fvg.get('age_bars', 0)} bars
"""
        else:
            prompt += "\nNo bullish FVGs within quality criteria\n"

        # Add bearish FVG info
        if fvg_context.get('nearest_bearish_fvg'):
            fvg = fvg_context['nearest_bearish_fvg']
            prompt += f"""
Nearest Bearish FVG (LONG opportunity):
  Zone: {fvg['bottom']:.2f} - {fvg['top']:.2f}
  Size: {fvg['size']:.2f} points
  Distance: {fvg['distance']:+.2f} points
  Age: {fvg.get('age_bars', 0)} bars
"""
        else:
            prompt += "\nNo bearish FVGs within quality criteria\n"

        # Add EMA trend analysis
        prompt += f"""
EMA TREND ANALYSIS:
EMA21:  {market_data.get('ema21', 0):.2f}
EMA75:  {market_data.get('ema75', 0):.2f}
EMA150: {market_data.get('ema150', 0):.2f}

Trend Alignment:
"""
        ema21 = market_data.get('ema21', 0)
        ema75 = market_data.get('ema75', 0)
        ema150 = market_data.get('ema150', 0)

        if ema21 > ema75 > ema150:
            prompt += "  Strong UPTREND (EMA21 > EMA75 > EMA150)\n"
        elif ema21 < ema75 < ema150:
            prompt += "  Strong DOWNTREND (EMA21 < EMA75 < EMA150)\n"
        elif ema21 > ema75:
            prompt += "  Weak uptrend (EMA21 > EMA75)\n"
        elif ema21 < ema75:
            prompt += "  Weak downtrend (EMA21 < EMA75)\n"
        else:
            prompt += "  Neutral/Choppy\n"

        # Add Stochastic momentum
        stoch = market_data.get('stochastic', 50)
        prompt += f"""
MOMENTUM INDICATOR:
Stochastic: {stoch:.2f}
"""
        if stoch < 20:
            prompt += "  Status: OVERSOLD - Potential bounce/reversal up\n"
        elif stoch > 80:
            prompt += "  Status: OVERBOUGHT - Potential pullback/reversal down\n"
        elif stoch < 40:
            prompt += "  Status: Below midpoint - Building upward momentum\n"
        elif stoch > 60:
            prompt += "  Status: Above midpoint - Building downward momentum\n"
        else:
            prompt += "  Status: Neutral zone\n"

        # Add memory context if available
        if memory_context:
            prompt += f"""
HISTORICAL PERFORMANCE:
"""
            if memory_context.get('fvg_only_stats'):
                stats = memory_context['fvg_only_stats']
                prompt += f"""
FVG-Only Trades: {stats['total_trades']} trades, {stats['win_rate']*100:.1f}% win rate
Average R/R: {stats['avg_rr']:.2f}:1
"""

        # Add decision criteria
        prompt += f"""
DECISION CRITERIA:
==================
- Minimum Risk/Reward: {self.min_risk_reward}:1
- Stop Loss Range: {self.stop_loss_min}-{self.stop_loss_max} points
- Recommended Stop: {self.stop_loss_default} points (NQ appropriate)
- Stop Buffer: {self.stop_buffer} points beyond FVG zone
- Confidence Threshold: {self.confidence_threshold}

ANALYSIS REQUIRED:
==================
You MUST provide a COMPLETE response with both long_assessment and short_assessment.

IMPORTANT: If you don't see a quality setup, that's COMPLETELY ACCEPTABLE.
- Use status: "none" for assessments with no valid setup
- Use status: "waiting" for setups you're monitoring but not ready to trade
- Use status: "ready" for setups that meet all criteria and are tradeable NOW

For EACH assessment (long and short):
1. Determine status: "none", "waiting", or "ready"
2. If status is NOT "none", provide:
   - Entry price (targeting FVG zone)
   - Stop loss placement:
     * CRITICAL: Base stop size on TARGET DISTANCE, not tight FVG bounds
     * Use 30-40% of target distance for stop (e.g., 100pt target = 35pt stop)
     * Avoid tight stops that get stopped out on normal volatility
     * Stop should allow room for price action while maintaining positive R/R
   - Target price (FVG fill or key level)
   - Risk/Reward ratio (minimum {self.min_risk_reward}:1)
   - Confidence level (0.0-1.0)
   - Reasoning explaining the setup and what you're waiting for
3. If status is "none", explain why no setup exists

Update Your Assessment Based On:
- What changed from previous analysis?
- FVG quality and proximity
- EMA trend alignment
- Stochastic momentum confirmation
- How long you've been tracking this setup (setup_age_bars)
- Whether you should keep waiting or abandon the setup

STOP LOSS PHILOSOPHY:
- Wider stops (30-50 points) allow breathing room
- Base stop distance on target distance, NOT on tight technical levels
- Getting stopped out frequently is worse than larger stop size
- Protect against extended moves, not normal volatility

Respond in JSON format:
{{
    "current_bar_index": <increment from previous or 0 if first>,
    "overall_bias": "bullish" | "bearish" | "neutral",
    "waiting_for": "<describe what you're waiting for, or 'No quality setup' if none>",

    "long_assessment": {{
        "status": "none" | "waiting" | "ready",
        "target_fvg": <FVG dict if applicable, else null>,
        "entry_plan": <price or null>,
        "stop_plan": <price or null>,
        "target_plan": <price or null>,
        "risk_reward": <ratio or null>,
        "confidence": <0.0-1.0>,
        "reasoning": "<detailed explanation of this assessment>"
    }},

    "short_assessment": {{
        "status": "none" | "waiting" | "ready",
        "target_fvg": <FVG dict if applicable, else null>,
        "entry_plan": <price or null>,
        "stop_plan": <price or null>,
        "target_plan": <price or null>,
        "risk_reward": <ratio or null>,
        "confidence": <0.0-1.0>,
        "reasoning": "<detailed explanation of this assessment>"
    }},

    "primary_decision": "LONG" | "SHORT" | "NONE",
    "overall_reasoning": "<incremental update: what changed from previous bar, should we trade or continue waiting>",

    "long_setup": {{
        "entry": <price from long_assessment>,
        "stop": <price from long_assessment>,
        "target": <price from long_assessment>,
        "risk_reward": <ratio from long_assessment>,
        "confidence": <confidence from long_assessment>,
        "reasoning": "<reasoning from long_assessment>"
    }},

    "short_setup": {{
        "entry": <price from short_assessment>,
        "stop": <price from short_assessment>,
        "target": <price from short_assessment>,
        "risk_reward": <ratio from short_assessment>,
        "confidence": <confidence from short_assessment>,
        "reasoning": "<reasoning from short_assessment>"
    }}
}}

IMPORTANT: The long_setup and short_setup fields must be populated for backward compatibility,
but your PRIMARY analysis should be in long_assessment and short_assessment.
Only set primary_decision to LONG/SHORT if the corresponding assessment status is "ready".
"""

        return prompt

    def parse_claude_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse Claude's JSON response

        Args:
            response_text: Raw response text from Claude

        Returns:
            Parsed decision dictionary or None if parsing fails
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            text = response_text.strip()
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()

            decision = json.loads(text)
            return decision
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}")
            return None

    def validate_decision(self, decision: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate Claude's trading decision

        Args:
            decision: Parsed decision dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields for new format
        # Support both old format (market_bias) and new format (overall_bias)
        if 'overall_bias' not in decision and 'market_bias' not in decision:
            return False, "Missing required field: overall_bias or market_bias"

        # Normalize to overall_bias for consistency
        if 'market_bias' in decision and 'overall_bias' not in decision:
            decision['overall_bias'] = decision['market_bias']

        required_fields = ['primary_decision', 'long_setup', 'short_setup', 'overall_reasoning']
        for field in required_fields:
            if field not in decision:
                return False, f"Missing required field: {field}"

        # Validate each setup
        for setup_name in ['long_setup', 'short_setup']:
            if setup_name not in decision:
                return False, f"Missing {setup_name} in decision"

            setup = decision[setup_name]
            if not isinstance(setup, dict):
                return False, f"{setup_name} is not a dictionary: {type(setup)}"

            setup_fields = ['entry', 'stop', 'target', 'risk_reward', 'confidence', 'reasoning']
            for field in setup_fields:
                if field not in setup:
                    return False, f"Missing field in {setup_name}: {field}"

        # If no trade, validation passes
        if decision['primary_decision'] == 'NONE':
            return True, None

        # Get the chosen setup
        chosen_setup = decision['long_setup'] if decision['primary_decision'] == 'LONG' else decision['short_setup']

        # Validate stop loss range
        entry = chosen_setup['entry']
        stop = chosen_setup['stop']
        stop_distance = abs(entry - stop)

        if stop_distance < self.stop_loss_min:
            return False, f"Stop loss too tight: {stop_distance:.2f}pts (min: {self.stop_loss_min}pts)"

        if stop_distance > self.stop_loss_max:
            return False, f"Stop loss too wide: {stop_distance:.2f}pts (max: {self.stop_loss_max}pts)"

        # Validate stop direction
        if decision['primary_decision'] == 'LONG' and stop >= entry:
            return False, "Invalid LONG stop: stop must be below entry"

        if decision['primary_decision'] == 'SHORT' and stop <= entry:
            return False, "Invalid SHORT stop: stop must be above entry"

        # Validate risk/reward
        if chosen_setup['risk_reward'] < self.min_risk_reward:
            return False, f"Risk/reward too low: {chosen_setup['risk_reward']:.2f} (min: {self.min_risk_reward})"

        # Validate confidence
        if chosen_setup['confidence'] < self.confidence_threshold:
            return False, f"Confidence too low: {chosen_setup['confidence']:.2f} (min: {self.confidence_threshold})"

        return True, None

    def analyze_setup(
        self,
        fvg_context: Dict[str, Any],
        market_data: Dict[str, Any],
        memory_context: Optional[Dict[str, Any]] = None,
        previous_analysis: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main analysis method - queries Claude for trading decision

        Args:
            fvg_context: FVG market context
            market_data: Market indicators (EMA, Stochastic, etc.)
            memory_context: Past trade performance data
            previous_analysis: Previous analysis state (formatted string)

        Returns:
            Decision dictionary with validation status
        """
        # Build prompt
        prompt = self.build_prompt(fvg_context, market_data, memory_context, previous_analysis)

        try:
            # Show full prompt
            logger.info("="*60)
            logger.info("SENDING TO CLAUDE:")
            logger.info("="*60)
            logger.info(prompt)
            logger.info("="*60)

            # Show waiting message
            print("\nWaiting for Agent response", end='', flush=True)

            import threading
            import time

            # Animation flag
            waiting = True

            def animate_dots():
                while waiting:
                    for i in range(6):
                        if not waiting:
                            break
                        print('.', end='', flush=True)
                        time.sleep(0.5)
                    if waiting:
                        print('\r' + ' ' * 40 + '\r', end='', flush=True)
                        print("Waiting for Agent response", end='', flush=True)

            # Start animation in background
            anim_thread = threading.Thread(target=animate_dots, daemon=True)
            anim_thread.start()

            # Query Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Stop animation
            waiting = False
            time.sleep(0.1)  # Let animation thread finish
            print('\r' + ' ' * 40 + '\r', end='', flush=True)  # Clear line

            # Extract response text
            response_text = response.content[0].text

            # Show full response
            logger.info("="*60)
            logger.info("CLAUDE RESPONSE:")
            logger.info("="*60)
            logger.info(response_text)
            logger.info("="*60)

            # Wait 2 seconds before clearing screen
            time.sleep(2)

            # Parse response
            decision = self.parse_claude_response(response_text)

            if not decision:
                return {
                    'success': False,
                    'error': 'Failed to parse Claude response',
                    'raw_response': response_text
                }

            # Validate decision
            is_valid, error_msg = self.validate_decision(decision)

            result = {
                'success': is_valid,
                'decision': decision,
                'timestamp': datetime.now().isoformat(),
                'validation_error': error_msg,
                'fvg_context': fvg_context,  # Store for display
                'market_data': market_data   # Store for display
            }

            # Log validation result
            if is_valid:
                primary = decision.get('primary_decision', 'NONE')
                if primary != 'NONE':
                    chosen = decision['long_setup'] if primary == 'LONG' else decision['short_setup']
                    logger.info(f"VALIDATION PASSED: {primary} @ {chosen['entry']:.0f} | R:R {chosen['risk_reward']:.2f}:1 | Conf {chosen['confidence']:.2f}")
                else:
                    logger.info("VALIDATION PASSED: No trade recommended")
            else:
                logger.warning(f"VALIDATION FAILED: {error_msg}")

            return result

        except Exception as e:
            logger.error(f"Error querying Claude: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def format_decision_display(
        self,
        result: Dict[str, Any],
        current_price: float = None
    ) -> str:
        """Format decision for clean display"""
        if not result.get('success', False):
            error_msg = result.get('validation_error') or result.get('error') or 'Unknown error'

            # Show clean error with decision context if available
            lines = []
            lines.append("="*60)
            lines.append("VALIDATION FAILED")
            lines.append("="*60)
            lines.append(f"Error: {error_msg}")

            # Try to show what was attempted
            decision = result.get('decision', {})
            if decision:
                primary = decision.get('primary_decision', 'UNKNOWN')
                lines.append(f"\nAttempted: {primary}")

                if primary in ['LONG', 'SHORT']:
                    setup = decision.get('long_setup' if primary == 'LONG' else 'short_setup', {})
                    if setup:
                        lines.append(f"Entry: {setup.get('entry') or 0:.0f}")
                        lines.append(f"Stop: {setup.get('stop') or 0:.0f}")
                        lines.append(f"Target: {setup.get('target') or 0:.0f}")
                        lines.append(f"R:R: {setup.get('risk_reward') or 0:.2f}:1")
                        lines.append(f"Confidence: {setup.get('confidence') or 0:.2f}")

            lines.append("\n" + "="*60)
            lines.append("Trade rejected - criteria not met")
            lines.append("="*60)

            return "\n".join(lines)

        decision = result['decision']
        fvg_context = result.get('fvg_context', {})
        market_data = result.get('market_data', {})

        # Use current price if provided, otherwise from context
        price = current_price or fvg_context.get('current_price', 0)

        # FVG info
        bull_fvg = fvg_context.get('nearest_bullish_fvg')
        bear_fvg = fvg_context.get('nearest_bearish_fvg')

        bull_str = f"UP {bull_fvg['bottom']:.0f}-{bull_fvg['top']:.0f} ({bull_fvg['distance']:+.0f}pts)" if bull_fvg else "None"
        bear_str = f"DN {bear_fvg['bottom']:.0f}-{bear_fvg['top']:.0f} ({bear_fvg['distance']:+.0f}pts)" if bear_fvg else "None"

        # Trend
        ema21 = market_data.get('ema21', 0)
        ema75 = market_data.get('ema75', 0)
        ema150 = market_data.get('ema150', 0)

        if ema21 > ema75 > ema150:
            trend = "Strong UP"
        elif ema21 < ema75 < ema150:
            trend = "Strong DN"
        elif ema21 > ema75:
            trend = "Weak UP"
        elif ema21 < ema75:
            trend = "Weak DN"
        else:
            trend = "Neutral"

        stoch = market_data.get('stochastic', 50)

        # Build display
        lines = []
        lines.append("="*60)
        lines.append(f"NQ @ {price:.2f}")
        lines.append("="*60)
        lines.append(f"FVG: {bull_str} | {bear_str}")
        lines.append(f"EMA: {trend} | Stoch: {stoch:.0f}")
        # Support both old and new format
        bias = decision.get('overall_bias') or decision.get('market_bias', 'unknown')
        lines.append(f"Market Bias: {bias.upper()}")
        lines.append("="*60)

        # Show both setups
        long_setup = decision.get('long_setup', {})
        short_setup = decision.get('short_setup', {})

        lines.append("\nLONG SETUP:")
        lines.append(f"  Entry: {long_setup.get('entry') or 0:.0f} | Stop: {long_setup.get('stop') or 0:.0f} | Target: {long_setup.get('target') or 0:.0f}")
        lines.append(f"  R:R {long_setup.get('risk_reward') or 0:.1f}:1 | Confidence: {long_setup.get('confidence') or 0:.2f}")
        lines.append(f"  {long_setup.get('reasoning', 'N/A')}")

        lines.append("\nSHORT SETUP:")
        lines.append(f"  Entry: {short_setup.get('entry') or 0:.0f} | Stop: {short_setup.get('stop') or 0:.0f} | Target: {short_setup.get('target') or 0:.0f}")
        lines.append(f"  R:R {short_setup.get('risk_reward') or 0:.1f}:1 | Confidence: {short_setup.get('confidence') or 0:.2f}")
        lines.append(f"  {short_setup.get('reasoning', 'N/A')}")

        lines.append("\n" + "="*60)

        # Primary decision
        primary = decision.get('primary_decision', 'NONE')
        if primary == 'NONE':
            lines.append(f"PRIMARY DECISION: NONE")
        else:
            chosen = long_setup if primary == 'LONG' else short_setup
            lines.append(f"PRIMARY DECISION: {primary} @ {chosen.get('entry') or 0:.0f} -> {chosen.get('target') or 0:.0f}")
            lines.append(f"Confidence: {chosen.get('confidence') or 0:.2f}")

        lines.append(f"\nOVERALL ANALYSIS:")
        lines.append(decision.get('overall_reasoning', 'N/A'))

        lines.append("\n" + "="*60)

        # Show trade signal status
        if primary != 'NONE':
            lines.append("STATUS: TRADE SIGNAL WRITTEN TO CSV")
        else:
            lines.append("STATUS: NO TRADE SIGNAL")

        lines.append("="*60)

        return "\n".join(lines)

    def get_decision_summary(self, result: Dict[str, Any]) -> str:
        """
        Generate human-readable summary of decision

        Args:
            result: Result dictionary from analyze_setup()

        Returns:
            Summary string
        """
        if not result['success']:
            return f"ANALYSIS FAILED: {result.get('error', 'Unknown error')}"

        decision = result['decision']

        if decision['decision'] == 'NONE':
            return f"NO TRADE\nReason: {decision['reasoning']}"

        lines = []
        lines.append(f"=== TRADE SIGNAL: {decision['decision']} ===")
        lines.append(f"Entry: {decision['entry']:.2f}")
        lines.append(f"Stop: {decision['stop']:.2f} ({abs(decision['entry'] - decision['stop']):.2f}pts)")
        lines.append(f"Target: {decision['target']:.2f} ({abs(decision['target'] - decision['entry']):.2f}pts)")
        lines.append(f"Risk/Reward: {decision['risk_reward']:.2f}:1")
        lines.append(f"Confidence: {decision['confidence']:.2%}")
        lines.append(f"Setup Type: {decision['setup_type']}")
        lines.append(f"\nReasoning:\n{decision['reasoning']}")

        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Sample config
    config = {
        'trading_params': {
            'min_risk_reward': 3.0,
            'confidence_threshold': 0.65
        },
        'risk_management': {
            'stop_loss_min': 15,
            'stop_loss_default': 20,
            'stop_loss_max': 50,
            'stop_buffer': 5
        }
    }

    # Sample contexts
    fvg_context = {
        'current_price': 14685.50,
        'nearest_bullish_fvg': {
            'top': 14715, 'bottom': 14710, 'size': 5.0,
            'distance': 29.50, 'age_bars': 12
        },
        'nearest_bearish_fvg': {
            'top': 14655, 'bottom': 14650, 'size': 5.0,
            'distance': 30.50, 'age_bars': 45
        }
    }

    level_context = {
        'nearest_level_above': 14700,
        'distance_to_level_above': 14.50,
        'nearest_level_below': 14600,
        'distance_to_level_below': 85.50,
        'on_level': False,
        'nearby_levels': [14700, 14600, 14800]
    }

    # NOTE: Requires ANTHROPIC_API_KEY environment variable
    # agent = TradingAgent(config)
    # result = agent.analyze_setup(fvg_context, level_context)
    # print(agent.get_decision_summary(result))
