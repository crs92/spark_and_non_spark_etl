"""TPC-H data generation module.

This module provides functionality for generating TPC-H benchmark data
at various scale factors and writing it to S3.
"""

# Import available modules
try:
    from src.generation.tpch_generator import TPCHGenerator

    __all__ = ["TPCHGenerator"]
except ImportError:
    # TPCHGenerator not yet implemented
    __all__ = []

try:
    from src.generation.tpchgen_wrapper import TPCHGenWrapper  # noqa: F401

    __all__.append("TPCHGenWrapper")
except ImportError:
    # TPCHGenWrapper not yet implemented
    pass
