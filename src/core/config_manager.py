"""
Enterprise Configuration Manager
Centralized configuration with validation and hot-reload support
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

from .exceptions import ConfigurationError


@dataclass
class TradingConfig:
    """Validated trading configuration"""
    min_gap_size: float
    max_gap_age_bars: int
    min_risk_reward: float
    confidence_threshold: float
    position_size: int
    max_slippage_points: float


@dataclass
class RiskConfig:
    """Validated risk management configuration"""
    stop_loss_min: int
    stop_loss_default: int
    stop_loss_max: int
    stop_buffer: int
    max_daily_trades: int
    max_daily_loss: float
    max_consecutive_losses: int
    max_position_size: int
    max_drawdown_percent: float
    cool_down_after_loss_minutes: int


@dataclass
class ClaudeConfig:
    """Claude API configuration"""
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    max_retries: int


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    health_check_interval_seconds: int
    heartbeat_file: str
    alert_on_no_signal_minutes: int
    log_performance_interval_minutes: int


class ConfigManager:
    """
    Enterprise-grade configuration manager with validation,
    hot-reload support, and environment override capabilities
    """

    _instance: Optional['ConfigManager'] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        """Singleton pattern for configuration"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        config_path: str = "config/agent_config.json",
        risk_rules_path: str = "config/risk_rules.json",
        force_reload: bool = False
    ):
        if self._initialized and not force_reload:
            return

        self.config_path = Path(config_path)
        self.risk_rules_path = Path(risk_rules_path)
        self._raw_config: Dict[str, Any] = {}
        self._raw_risk_rules: Dict[str, Any] = {}
        self._last_loaded: Optional[datetime] = None
        self._validation_errors: List[str] = []

        # Load and validate configuration
        self._load_configs()
        self._validate_configs()
        self._apply_environment_overrides()

        # Create typed configuration objects
        self._create_typed_configs()

        self._initialized = True

    def _load_configs(self):
        """Load configuration files"""
        try:
            if not self.config_path.exists():
                raise ConfigurationError(
                    f"Configuration file not found: {self.config_path}",
                    config_key="config_path"
                )

            with open(self.config_path, 'r') as f:
                self._raw_config = json.load(f)

            if self.risk_rules_path.exists():
                with open(self.risk_rules_path, 'r') as f:
                    self._raw_risk_rules = json.load(f)

            self._last_loaded = datetime.now()

        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in configuration file: {e}",
                config_key="json_parse"
            )

    def _validate_configs(self):
        """Validate configuration values and consistency"""
        self._validation_errors = []

        # Required sections
        required_sections = ['trading_params', 'risk_management', 'claude']
        for section in required_sections:
            if section not in self._raw_config:
                self._validation_errors.append(f"Missing required section: {section}")

        if self._validation_errors:
            raise ConfigurationError(
                f"Configuration validation failed: {'; '.join(self._validation_errors)}",
                config_key="validation"
            )

        # Validate risk parameters consistency
        trading = self._raw_config.get('trading_params', {})
        risk = self._raw_config.get('risk_management', {})

        # Stop loss range validation
        if risk.get('stop_loss_min', 0) >= risk.get('stop_loss_max', 100):
            self._validation_errors.append(
                "stop_loss_min must be less than stop_loss_max"
            )

        # Risk/reward must be positive
        if trading.get('min_risk_reward', 0) <= 0:
            self._validation_errors.append(
                "min_risk_reward must be greater than 0"
            )

        # Confidence threshold must be between 0 and 1
        conf = trading.get('confidence_threshold', 0.65)
        if not 0 < conf <= 1:
            self._validation_errors.append(
                "confidence_threshold must be between 0 and 1"
            )

        if self._validation_errors:
            raise ConfigurationError(
                f"Configuration validation failed: {'; '.join(self._validation_errors)}",
                config_key="validation"
            )

    def _apply_environment_overrides(self):
        """Apply environment variable overrides"""
        env_mappings = {
            'CLAUDE_MODEL': ('claude', 'model'),
            'MAX_DAILY_TRADES': ('risk_management', 'max_daily_trades'),
            'MAX_DAILY_LOSS': ('risk_management', 'max_daily_loss'),
            'MIN_RISK_REWARD': ('trading_params', 'min_risk_reward'),
            'CONFIDENCE_THRESHOLD': ('trading_params', 'confidence_threshold'),
            'POSITION_SIZE': ('trading_params', 'position_size'),
        }

        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    # Attempt to parse as number
                    if '.' in value:
                        value = float(value)
                    else:
                        try:
                            value = int(value)
                        except ValueError:
                            pass  # Keep as string

                    if section in self._raw_config:
                        self._raw_config[section][key] = value

                except (ValueError, TypeError):
                    pass  # Keep original value

    def _create_typed_configs(self):
        """Create typed configuration objects"""
        trading = self._raw_config.get('trading_params', {})
        risk = self._raw_config.get('risk_management', {})
        claude = self._raw_config.get('claude', {})
        monitoring = self._raw_config.get('monitoring', {})

        self.trading = TradingConfig(
            min_gap_size=trading.get('min_gap_size', 5.0),
            max_gap_age_bars=trading.get('max_gap_age_bars', 1000),
            min_risk_reward=trading.get('min_risk_reward', 3.0),
            confidence_threshold=trading.get('confidence_threshold', 0.65),
            position_size=trading.get('position_size', 1),
            max_slippage_points=trading.get('max_slippage_points', 2.0)
        )

        self.risk = RiskConfig(
            stop_loss_min=risk.get('stop_loss_min', 15),
            stop_loss_default=risk.get('stop_loss_default', 35),
            stop_loss_max=risk.get('stop_loss_max', 50),
            stop_buffer=risk.get('stop_buffer', 5),
            max_daily_trades=risk.get('max_daily_trades', 5),
            max_daily_loss=risk.get('max_daily_loss', 100),
            max_consecutive_losses=risk.get('max_consecutive_losses', 3),
            max_position_size=risk.get('max_position_size', 10),
            max_drawdown_percent=risk.get('max_drawdown_percent', 5.0),
            cool_down_after_loss_minutes=risk.get('cool_down_after_loss_minutes', 15)
        )

        self.claude = ClaudeConfig(
            model=claude.get('model', 'claude-sonnet-4-5-20250929'),
            temperature=claude.get('temperature', 0.3),
            max_tokens=claude.get('max_tokens', 2000),
            timeout_seconds=claude.get('timeout_seconds', 60),
            max_retries=claude.get('max_retries', 3)
        )

        self.monitoring = MonitoringConfig(
            health_check_interval_seconds=monitoring.get('health_check_interval_seconds', 30),
            heartbeat_file=monitoring.get('heartbeat_file', 'data/.heartbeat'),
            alert_on_no_signal_minutes=monitoring.get('alert_on_no_signal_minutes', 120),
            log_performance_interval_minutes=monitoring.get('log_performance_interval_minutes', 60)
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key"""
        keys = key.split('.')
        value = self._raw_config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    def get_file_path(self, key: str) -> Path:
        """Get file path from configuration"""
        file_paths = self._raw_config.get('file_paths', {})
        path = file_paths.get(key)
        if path:
            return Path(path)
        raise ConfigurationError(f"File path not configured: {key}", config_key=key)

    def get_risk_rules(self) -> Dict[str, Any]:
        """Get risk rules configuration"""
        return self._raw_risk_rules.copy()

    def reload(self) -> bool:
        """Hot-reload configuration"""
        try:
            self._load_configs()
            self._validate_configs()
            self._apply_environment_overrides()
            self._create_typed_configs()
            return True
        except ConfigurationError:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Export full configuration as dictionary"""
        return {
            "config": self._raw_config,
            "risk_rules": self._raw_risk_rules,
            "last_loaded": self._last_loaded.isoformat() if self._last_loaded else None
        }

    @classmethod
    def reset(cls):
        """Reset singleton instance (for testing)"""
        cls._instance = None
        cls._initialized = False
