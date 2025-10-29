"""Simple and clean timing decorator for ETL pipelines.

This module provides a decorator-based approach to timing ETL operations
without cluttering the main pipeline code.
"""

import functools
import logging
import time
from collections.abc import Callable

import psutil

logger = logging.getLogger(__name__)


class PipelineTimer:
    """Simple timer for ETL pipeline operations."""

    def __init__(self, framework: str, mode: str):
        """Initialize pipeline timer.

        Args:
            framework: Framework name (polars, spark)
            mode: Processing mode (bulk, incremental)
        """
        self.framework = framework
        self.mode = mode
        self.metrics = {
            "framework": framework,
            "mode": mode,
            "startup_time": 0.0,
            "extract": {"total": 0.0, "file_discovery": 0.0, "file_read": 0.0},
            "transform": {
                "total": 0.0,
                "quality_checks": 0.0,
                "sessionization": 0.0,
            },
            "load": {"total": 0.0, "merge": 0.0, "write": 0.0},
            "total_time": 0.0,
            "resources": {
                "peak_memory_mb": 0.0,
                "avg_memory_mb": 0.0,
            },
        }
        self.process = psutil.Process()
        self.memory_samples = []
        self.pipeline_start = None

    def start_pipeline(self):
        """Mark the start of the pipeline."""
        self.pipeline_start = time.time()

    def end_pipeline(self):
        """Mark the end of the pipeline and calculate totals."""
        if self.pipeline_start:
            self.metrics["total_time"] = time.time() - self.pipeline_start

        # Calculate resource metrics
        if self.memory_samples:
            self.metrics["resources"]["peak_memory_mb"] = max(self.memory_samples)
            self.metrics["resources"]["avg_memory_mb"] = sum(self.memory_samples) / len(
                self.memory_samples
            )

    def sample_memory(self):
        """Sample current memory usage."""
        try:
            memory_mb = self.process.memory_info().rss / 1024 / 1024
            self.memory_samples.append(memory_mb)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def log_summary(self):
        """Log a summary of timing metrics."""
        # Print to both logger and stdout to ensure it's captured
        summary = [
            "=" * 80,
            f"TIMING SUMMARY - {self.framework.upper()} ({self.mode})",
            "=" * 80,
            f"Total Time: {self.metrics['total_time']:.2f}s",
            f"  Startup: {self.metrics['startup_time']:.2f}s",
            f"  Extract: {self.metrics['extract']['total']:.2f}s",
            f"  Transform: {self.metrics['transform']['total']:.2f}s",
            f"  Load: {self.metrics['load']['total']:.2f}s",
            "-" * 80,
            (
                f"Peak Memory: {self.metrics['resources']['peak_memory_mb']:.2f} MB | "
                f"Avg: {self.metrics['resources']['avg_memory_mb']:.2f} MB"
            ),
            "=" * 80,
        ]

        # Log to logger
        for line in summary:
            logger.info(line)

        # Also print to stdout to ensure it's captured
        print("\n".join(summary), flush=True)


def timed_phase(phase: str, subphase: str | None = None):
    """Decorator to time a pipeline phase or subphase.

    Args:
        phase: Phase name (extract, transform, load)
        subphase: Optional subphase name (file_discovery, quality_checks, etc.)

    Usage:
        @timed_phase("extract", "file_read")
        def read_data(self):
            # Your code here
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get timer from instance
            timer = getattr(self, "_timer", None)
            if not timer:
                # No timer attached, just run the function
                return func(self, *args, **kwargs)

            start = time.time()
            result = func(self, *args, **kwargs)
            elapsed = time.time() - start

            # Record timing
            if subphase:
                timer.metrics[phase][subphase] = elapsed
            else:
                timer.metrics[phase]["total"] = elapsed

            # Sample memory after operation
            timer.sample_memory()

            return result

        return wrapper

    return decorator


def timed_startup(func: Callable) -> Callable:
    """Decorator to time startup/initialization phase.

    Usage:
        @timed_startup
        def __init__(self, ...):
            # Your initialization code
            pass
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        start = time.time()
        result = func(self, *args, **kwargs)

        # Record startup time if timer exists
        timer = getattr(self, "_timer", None)
        if timer:
            timer.metrics["startup_time"] = time.time() - start

        return result

    return wrapper
