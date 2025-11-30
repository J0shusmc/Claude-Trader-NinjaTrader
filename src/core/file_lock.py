"""
Enterprise File Locking
Thread-safe and process-safe file operations
"""

import os
import time
import fcntl
import json
import csv
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Union
from contextlib import contextmanager
from functools import wraps
from datetime import datetime

from .exceptions import FileOperationError

T = TypeVar('T')


class FileLock:
    """
    Cross-platform file locking mechanism
    Provides both shared (read) and exclusive (write) locks
    """

    def __init__(self, file_path: Union[str, Path], timeout: float = 30.0):
        """
        Initialize file lock

        Args:
            file_path: Path to file to lock
            timeout: Maximum time to wait for lock (seconds)
        """
        self.file_path = Path(file_path)
        self.lock_path = self.file_path.with_suffix(self.file_path.suffix + '.lock')
        self.timeout = timeout
        self._lock_file = None
        self._locked = False

    def _ensure_lock_file(self):
        """Ensure lock file directory exists"""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.lock_path.exists():
            self.lock_path.touch()

    @contextmanager
    def read_lock(self):
        """Acquire shared read lock"""
        self._ensure_lock_file()
        start_time = time.time()

        try:
            self._lock_file = open(self.lock_path, 'r')

            while True:
                try:
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                    self._locked = True
                    break
                except (IOError, OSError):
                    if time.time() - start_time > self.timeout:
                        raise FileOperationError(
                            f"Timeout acquiring read lock after {self.timeout}s",
                            str(self.file_path),
                            "read_lock"
                        )
                    time.sleep(0.1)

            yield

        finally:
            self._release()

    @contextmanager
    def write_lock(self):
        """Acquire exclusive write lock"""
        self._ensure_lock_file()
        start_time = time.time()

        try:
            self._lock_file = open(self.lock_path, 'w')

            while True:
                try:
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._locked = True
                    break
                except (IOError, OSError):
                    if time.time() - start_time > self.timeout:
                        raise FileOperationError(
                            f"Timeout acquiring write lock after {self.timeout}s",
                            str(self.file_path),
                            "write_lock"
                        )
                    time.sleep(0.1)

            yield

        finally:
            self._release()

    def _release(self):
        """Release the lock"""
        if self._lock_file:
            try:
                if self._locked:
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                    self._locked = False
                self._lock_file.close()
            except (IOError, OSError):
                pass
            finally:
                self._lock_file = None


def safe_file_operation(
    operation: str = "read",
    timeout: float = 30.0,
    retries: int = 3
):
    """
    Decorator for safe file operations with locking

    Args:
        operation: "read" or "write"
        timeout: Lock timeout in seconds
        retries: Number of retry attempts
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Extract file_path from args or kwargs
            file_path = kwargs.get('file_path') or (args[1] if len(args) > 1 else None)

            if file_path is None:
                # No file path, just call the function
                return func(*args, **kwargs)

            lock = FileLock(file_path, timeout=timeout)
            last_error = None

            for attempt in range(retries):
                try:
                    if operation == "write":
                        with lock.write_lock():
                            return func(*args, **kwargs)
                    else:
                        with lock.read_lock():
                            return func(*args, **kwargs)

                except FileOperationError as e:
                    last_error = e
                    if attempt < retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                    continue

            raise last_error or FileOperationError(
                f"Failed after {retries} attempts",
                str(file_path),
                operation
            )

        return wrapper
    return decorator


class SafeFileHandler:
    """
    Thread-safe file handler for CSV and JSON operations
    """

    @staticmethod
    @safe_file_operation(operation="read")
    def read_json(file_path: Union[str, Path]) -> dict:
        """Read JSON file with locking"""
        path = Path(file_path)
        if not path.exists():
            return {}

        with open(path, 'r') as f:
            return json.load(f)

    @staticmethod
    @safe_file_operation(operation="write")
    def write_json(file_path: Union[str, Path], data: dict, indent: int = 2):
        """Write JSON file with locking"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(data, f, indent=indent, default=str)

    @staticmethod
    @safe_file_operation(operation="read")
    def read_csv(file_path: Union[str, Path]) -> list:
        """Read CSV file with locking"""
        path = Path(file_path)
        if not path.exists():
            return []

        with open(path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            return list(reader)

    @staticmethod
    @safe_file_operation(operation="write")
    def write_csv(
        file_path: Union[str, Path],
        data: list,
        fieldnames: list,
        mode: str = 'w'
    ):
        """Write CSV file with locking"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        file_exists = path.exists() and path.stat().st_size > 0

        with open(path, mode, newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if mode == 'w' or not file_exists:
                writer.writeheader()

            if isinstance(data, list):
                writer.writerows(data)
            else:
                writer.writerow(data)

    @staticmethod
    @safe_file_operation(operation="write")
    def append_csv(file_path: Union[str, Path], row: dict, fieldnames: list):
        """Append row to CSV file with locking"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        file_exists = path.exists() and path.stat().st_size > 0

        with open(path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow(row)

    @staticmethod
    def atomic_write(file_path: Union[str, Path], content: str):
        """
        Atomic file write using temporary file and rename
        Ensures file is never in a partial state
        """
        path = Path(file_path)
        temp_path = path.with_suffix(path.suffix + '.tmp')

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(temp_path, 'w') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            os.rename(temp_path, path)

        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise FileOperationError(
                f"Atomic write failed: {e}",
                str(file_path),
                "atomic_write"
            )
