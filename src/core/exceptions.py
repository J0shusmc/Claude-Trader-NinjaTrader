"""
Enterprise Exception Hierarchy
Custom exceptions for the trading system
"""

from typing import Optional, Dict, Any
from datetime import datetime


class TradingError(Exception):
    """Base exception for all trading-related errors"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recoverable: bool = True
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "TRADING_ERROR"
        self.details = details or {}
        self.recoverable = recoverable
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp
        }

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


class ConfigurationError(TradingError):
    """Configuration-related errors"""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            error_code="CONFIG_ERROR",
            details={"config_key": config_key, **kwargs.get("details", {})},
            recoverable=False
        )


class RiskLimitError(TradingError):
    """Risk limit violations"""

    def __init__(
        self,
        message: str,
        limit_type: str,
        current_value: float,
        limit_value: float,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="RISK_LIMIT_VIOLATED",
            details={
                "limit_type": limit_type,
                "current_value": current_value,
                "limit_value": limit_value,
                **kwargs.get("details", {})
            },
            recoverable=True
        )
        self.limit_type = limit_type
        self.current_value = current_value
        self.limit_value = limit_value


class SignalValidationError(TradingError):
    """Signal validation failures"""

    def __init__(
        self,
        message: str,
        signal_data: Optional[Dict[str, Any]] = None,
        validation_rule: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="SIGNAL_VALIDATION_FAILED",
            details={
                "signal_data": signal_data,
                "validation_rule": validation_rule,
                **kwargs.get("details", {})
            },
            recoverable=True
        )


class APIError(TradingError):
    """External API errors (Claude, broker, etc.)"""

    def __init__(
        self,
        message: str,
        api_name: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="API_ERROR",
            details={
                "api_name": api_name,
                "status_code": status_code,
                "response_body": response_body,
                **kwargs.get("details", {})
            },
            recoverable=True
        )
        self.api_name = api_name
        self.status_code = status_code


class FileOperationError(TradingError):
    """File operation errors"""

    def __init__(
        self,
        message: str,
        file_path: str,
        operation: str,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="FILE_OPERATION_ERROR",
            details={
                "file_path": file_path,
                "operation": operation,
                **kwargs.get("details", {})
            },
            recoverable=True
        )
        self.file_path = file_path
        self.operation = operation


class PositionError(TradingError):
    """Position management errors"""

    def __init__(
        self,
        message: str,
        position_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="POSITION_ERROR",
            details={"position_id": position_id, **kwargs.get("details", {})},
            recoverable=True
        )


class ReconciliationError(TradingError):
    """Trade reconciliation errors"""

    def __init__(
        self,
        message: str,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        **kwargs
    ):
        super().__init__(
            message,
            error_code="RECONCILIATION_ERROR",
            details={
                "expected": expected,
                "actual": actual,
                **kwargs.get("details", {})
            },
            recoverable=False
        )


class CircuitBreakerError(TradingError):
    """Circuit breaker triggered"""

    def __init__(
        self,
        message: str,
        trigger_reason: str,
        cooldown_until: Optional[datetime] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="CIRCUIT_BREAKER_TRIGGERED",
            details={
                "trigger_reason": trigger_reason,
                "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
                **kwargs.get("details", {})
            },
            recoverable=True
        )
        self.cooldown_until = cooldown_until
