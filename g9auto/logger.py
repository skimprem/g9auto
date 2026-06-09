"""
Logging module for g9auto with verbose mode support.
Supports file logging and optional console output.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


class g9Logger:
    """Custom logger with verbose mode and section formatting."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if g9Logger._initialized:
            return

        self.logger = logging.getLogger('g9auto')
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        self.verbose = False
        self._file_handler = None
        self._console_handler = None
        self._current_section = None

        g9Logger._initialized = True

    def setup(self, log_dir: str = 'logs', verbose: bool = False, console: bool = True, log_to_file: bool = True):
        """
        Configure the logger.

        Args:
            log_dir: Directory for log files
            verbose: If True, duplicate logs to console
            console: If True, enable console logging
            log_to_file: If True, write logs to file
        """
        self.verbose = verbose

        # Clear existing handlers
        self.logger.handlers.clear()

        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # File handler
        if log_to_file:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = log_path / f'g9auto_{timestamp}.log'

            self._file_handler = logging.FileHandler(log_file, encoding='utf-8')
            self._file_handler.setLevel(logging.DEBUG)
            self._file_handler.setFormatter(file_formatter)
            self.logger.addHandler(self._file_handler)

        # Console handler (only if verbose)
        if console:
            self._console_handler = logging.StreamHandler(sys.stdout)

            if verbose:
                self._console_handler.setLevel(logging.DEBUG)
            else:
                self._console_handler.setLevel(logging.INFO)

            self._console_handler.setFormatter(console_formatter)
            self.logger.addHandler(self._console_handler)

        return self

    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)

    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)

    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    def section(self, title: str):
        """Log a section header."""
        self._current_section = title
    
    def _format(self, message: str) -> str:
        """Format message with current section if applicable."""
        if self._current_section:
            return f"[{self._current_section}] {message}"
        return message

    def ok(self, message: str):
        """Log success message with [OK] prefix."""
        self.logger.debug(self._format(f"[OK] {message}"))

    def fail(self, message: str):
        """Log failure message with [FAIL] prefix."""
        self.logger.error(self._format(f"[FAIL] {message}"))

    def success(self, message: str):
        """Log final success message."""
        self.logger.info("[SUCCESS] %s", message)

    def project_info(self, path: str, station: str):
        """Log project opening information."""
        self.logger.info("Station: %s", station)
        self.logger.info("Project: %s", path)


# Global logger instance
_logger = None


def get_logger() -> g9Logger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = g9Logger()
    return _logger


def setup_logging(log_dir: str = 'logs', verbose: bool = False, console: bool = True, log_to_file: bool = True) -> g9Logger:
    """
    Setup and configure the global logger.

    Args:
        log_dir: Directory for log files
        verbose: If True, duplicate logs to console
        console: If True, enable console logging
        log_to_file: If True, write logs to file

    Returns:
        Configured logger instance
    """
    logger = get_logger()
    logger.setup(log_dir=log_dir, verbose=verbose, console=console, log_to_file=log_to_file)
    return logger
