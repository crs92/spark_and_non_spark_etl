"""TPC-H data generation module.

This module provides functionality for generating TPC-H benchmark data
at various scale factors and writing it to S3.
"""

from src.generation.tpch_generator import TPCHGenerator

__all__ = ["TPCHGenerator"]
