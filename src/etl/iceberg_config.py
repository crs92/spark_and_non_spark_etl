"""Iceberg Configuration for Local Development.

This module provides configuration and utilities for working with Apache
Iceberg tables on a local machine using a file-based catalog.
"""

import logging
from pathlib import Path

from pyiceberg.catalog import load_catalog

logger = logging.getLogger(__name__)


class IcebergConfig:
    """Configuration for local Iceberg catalog."""

    def __init__(self, warehouse_path: str = "data/iceberg_warehouse"):
        """Initialize Iceberg configuration.

        Args:
            warehouse_path: Path to Iceberg warehouse directory
        """
        self.warehouse_path = Path(warehouse_path)
        self.warehouse_path.mkdir(parents=True, exist_ok=True)

        # Catalog configuration for local file-based catalog
        self.catalog_config = {
            "type": "sql",
            "uri": f"sqlite:///{self.warehouse_path}/catalog.db",
            "warehouse": f"file://{self.warehouse_path.absolute()}",
        }

    def get_catalog(self):
        """Get or create Iceberg catalog.

        Returns:
            Iceberg catalog instance
        """
        try:
            catalog = load_catalog("local", **self.catalog_config)
            logger.info("Connected to Iceberg catalog at %s", self.warehouse_path)

        except Exception as e:
            logger.error("Failed to load Iceberg catalog: %s", e)
            raise
        return catalog


def get_default_iceberg_config() -> IcebergConfig:
    """Get default Iceberg configuration for local development.

    Returns:
        IcebergConfig instance with default settings
    """
    return IcebergConfig()
