"""Simple data generation module for ETL benchmark testing."""

from .generator import (
    ClickstreamDataGenerator,
    DataSize,
    generate_benchmark_data,
)

__all__ = [
    "ClickstreamDataGenerator",
    "DataSize",
    "generate_benchmark_data",
]
