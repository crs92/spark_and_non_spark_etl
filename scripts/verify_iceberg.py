#!/usr/bin/env python3
"""Verify Iceberg Table Implementation.

This script verifies that the Iceberg table is properly configured and
contains data.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import polars as pl

from src.etl.iceberg_config import IcebergConfig


def verify_iceberg_table():
    """Verify Iceberg table setup and data."""
    print("=" * 80)
    print("ICEBERG TABLE VERIFICATION")
    print("=" * 80)

    # Initialize config
    config = IcebergConfig()

    print(f"\n📁 Warehouse Location: {config.warehouse_path}")
    print(f"📊 Catalog DB: {config.warehouse_path / 'catalog.db'}")

    # Check if warehouse exists
    if not config.warehouse_path.exists():
        print("\n❌ Iceberg warehouse not found!")
        print("   Run bulk load first:")
        print("   .venv/bin/python -m src.etl.polars_etl --mode bulk")
        return False

    try:
        # Load catalog
        catalog = config.get_catalog()
        print("\n✅ Iceberg catalog loaded successfully")

        # List namespaces
        namespaces = list(catalog.list_namespaces())
        print(f"\n📂 Namespaces: {namespaces}")

        # List tables
        if namespaces:
            for namespace in namespaces:
                tables = list(catalog.list_tables(namespace))
                print(f"   Tables in {namespace}: {[t[1] for t in tables]}")

        # Load table
        table_name = "etl.clickstream_events"
        try:
            table = catalog.load_table(table_name)
            print(f"\n✅ Table loaded: {table_name}")

            # Get table metadata
            print("\n📋 Table Metadata:")
            print(f"   Location: {table.location()}")
            print(f"   Schema: {len(table.schema().fields)} fields")

            # List fields
            print("\n📊 Schema Fields:")
            for field in table.schema().fields:
                required = "required" if field.required else "optional"
                print(f"   - {field.name}: {field.field_type} ({required})")

            # Scan table
            print("\n📈 Scanning table data...")
            scan = table.scan()
            arrow_table = scan.to_arrow()
            df = pl.from_arrow(arrow_table)

            print("\n✅ Data loaded successfully")
            print(f"   Total records: {len(df):,}")
            print(f"   Columns: {len(df.columns)}")

            # Show sample data
            print("\n📄 Sample Data (first 5 rows):")
            sample = df.select(
                ["event_id", "user_id", "timestamp", "session_id", "country", "device"]
            ).head(5)
            print(sample)

            # Show statistics
            print("\n📊 Statistics:")
            print(f"   Unique users: {df['user_id'].n_unique():,}")
            print(f"   Unique sessions: {df['session_id'].n_unique():,}")
            print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

            # Count by country
            print("\n🌍 Top 5 Countries:")
            country_counts = (
                df.group_by("country")
                .agg(pl.count().alias("count"))
                .sort("count", descending=True)
                .head(5)
            )
            print(country_counts)

            # Count by device
            print("\n📱 Device Distribution:")
            device_counts = (
                df.group_by("device")
                .agg(pl.count().alias("count"))
                .sort("count", descending=True)
            )
            print(device_counts)

            # Check data files
            data_path = Path(table.location().replace("file://", "")) / "data"
            if data_path.exists():
                parquet_files = list(data_path.glob("*.parquet"))
                print("\n📦 Data Files:")
                print(f"   Total Parquet files: {len(parquet_files)}")
                total_size = sum(f.stat().st_size for f in parquet_files)
                print(f"   Total size: {total_size / 1024 / 1024:.2f} MB")

            print("\n" + "=" * 80)
            print("✅ VERIFICATION SUCCESSFUL")
            print("=" * 80)
            res = True

        except Exception as e:
            print(f"\n❌ Failed to load table {table_name}: {e}")
            print("\n   Run bulk load first:")
            print("   .venv/bin/python -m src.etl.polars_etl --mode bulk")
            res = False

    except Exception as e:
        print(f"\n❌ Failed to load catalog: {e}")
        res = False
    return res


if __name__ == "__main__":
    success = verify_iceberg_table()
    sys.exit(0 if success else 1)
