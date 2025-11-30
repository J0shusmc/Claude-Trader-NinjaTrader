"""
Enterprise Logging Setup
Structured logging with correlation IDs, JSON output, and rotation
"""

import logging
import json
import sys
import uuid
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager
from functools import wraps

# Thread-local storage for correlation IDs
_context = threading.local()


class LogContext:
    """
    Context manager for correlation ID tracking
    Allows tracing requests/signals through the system
    """

    @staticmethod
    def get_correlation_id() -> str:
        """Get current correlation ID or generate new one"""
        return getattr(_context, 'correlation_id', None) or str(uuid.uuid4())[:8]

    @staticmethod
    def set_correlation_id(correlation_id: str):
        """Set correlation ID for current thread"""
        _context.correlation_id = correlation_id

    @staticmethod
    @contextmanager
    def correlation_scope(correlation_id: Optional[str] = None):
        """Context manager for correlation ID scope"""
        old_id = getattr(_context, 'correlation_id', None)
        _context.correlation_id = correlation_id or str(uuid.uuid4())[:8]
        try:
            yield _context.correlation_id
        finally:
            _context.correlation_id = old_id

    @staticmethod
    def get_context() -> Dict[str, Any]:
        """Get all context data"""
        return {
            'correlation_id': LogContext.get_correlation_id(),
            'trade_id': getattr(_context, 'trade_id', None),
            'signal_id': getattr(_context, 'signal_id', None),
        }

    @staticmethod
    def set_trade_id(trade_id: str):
        """Set current trade ID"""
        _context.trade_id = trade_id

    @staticmethod
    def set_signal_id(signal_id: str):
        """Set current signal ID"""
        _context.signal_id = signal_id


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': LogContext.get_correlation_id(),
        }

        # Add context data
        context = LogContext.get_context()
        if context.get('trade_id'):
            log_entry['trade_id'] = context['trade_id']
        if context.get('signal_id'):
            log_entry['signal_id'] = context['signal_id']

        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_entry['data'] = record.extra_data

        # Add exception info
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add source location
        log_entry['source'] = {
            'file': record.filename,
            'line': record.lineno,
            'function': record.funcName
        }

        return json.dumps(log_entry)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for better readability"""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        correlation_id = LogContext.get_correlation_id()

        # Format timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Build message
        message = record.getMessage()

        # Add context
        context_parts = []
        context = LogContext.get_context()
        if context.get('trade_id'):
            context_parts.append(f"trade={context['trade_id']}")
        if context.get('signal_id'):
            context_parts.append(f"signal={context['signal_id']}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""

        formatted = (
            f"{timestamp} | "
            f"{color}{record.levelname:8}{self.RESET} | "
            f"[{correlation_id}] "
            f"{record.name} - {message}{context_str}"
        )

        if record.exc_info:
            formatted += '\n' + self.formatException(record.exc_info)

        return formatted


class TradingLogger(logging.Logger):
    """Enhanced logger with extra data support"""

    def _log_with_data(
        self,
        level: int,
        msg: str,
        data: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ):
        """Log with optional structured data"""
        if data:
            kwargs.setdefault('extra', {})['extra_data'] = data
        super().log(level, msg, *args, **kwargs)

    def info_with_data(self, msg: str, data: Dict[str, Any] = None, *args, **kwargs):
        self._log_with_data(logging.INFO, msg, data, *args, **kwargs)

    def warning_with_data(self, msg: str, data: Dict[str, Any] = None, *args, **kwargs):
        self._log_with_data(logging.WARNING, msg, data, *args, **kwargs)

    def error_with_data(self, msg: str, data: Dict[str, Any] = None, *args, **kwargs):
        self._log_with_data(logging.ERROR, msg, data, *args, **kwargs)

    def trade_signal(self, direction: str, entry: float, stop: float, target: float, confidence: float):
        """Log trade signal with structured data"""
        self.info_with_data(
            f"TRADE SIGNAL: {direction}",
            {
                'direction': direction,
                'entry': entry,
                'stop': stop,
                'target': target,
                'confidence': confidence,
                'risk_reward': abs(target - entry) / abs(entry - stop) if entry != stop else 0
            }
        )

    def trade_executed(self, direction: str, price: float, quantity: int):
        """Log trade execution"""
        self.info_with_data(
            f"TRADE EXECUTED: {direction} {quantity}x @ {price}",
            {
                'direction': direction,
                'price': price,
                'quantity': quantity
            }
        )

    def trade_closed(self, direction: str, entry: float, exit_price: float, pnl: float, result: str):
        """Log trade close"""
        self.info_with_data(
            f"TRADE CLOSED: {result} - P/L: {pnl:+.2f}",
            {
                'direction': direction,
                'entry': entry,
                'exit': exit_price,
                'pnl': pnl,
                'result': result
            }
        )

    def risk_warning(self, limit_type: str, current: float, limit: float):
        """Log risk warning"""
        self.warning_with_data(
            f"RISK WARNING: {limit_type} approaching limit",
            {
                'limit_type': limit_type,
                'current_value': current,
                'limit_value': limit,
                'utilization_pct': (current / limit * 100) if limit > 0 else 100
            }
        )


# Set custom logger class
logging.setLoggerClass(TradingLogger)


def setup_enterprise_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True,
    enable_json: bool = True,
    max_size_mb: int = 50,
    backup_count: int = 5
) -> logging.Logger:
    """
    Setup enterprise-grade logging configuration

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        enable_console: Enable console output
        enable_json: Enable JSON logging to file
        max_size_mb: Maximum log file size in MB
        backup_count: Number of backup files to keep

    Returns:
        Root logger
    """
    # Create logs directory if needed
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler with colored output
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(ColoredFormatter())
        root_logger.addHandler(console_handler)

    # File handler with JSON formatting
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)  # Capture all in file

        if enable_json:
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s - %(message)s'
            ))

        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> TradingLogger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)


def log_function_call(logger: Optional[logging.Logger] = None):
    """Decorator to log function entry and exit"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = logger or logging.getLogger(func.__module__)
            func_name = func.__name__

            log.debug(f"Entering {func_name}")
            try:
                result = func(*args, **kwargs)
                log.debug(f"Exiting {func_name}")
                return result
            except Exception as e:
                log.error(f"Exception in {func_name}: {e}")
                raise

        return wrapper
    return decorator
