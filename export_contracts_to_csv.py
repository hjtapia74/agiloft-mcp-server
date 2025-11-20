#!/usr/bin/env python3
"""
Export Agiloft Contracts to CSV

This script connects to Agiloft using the API, retrieves all contracts,
and exports them to a CSV file.

Usage:
    python export_contracts_to_csv.py

Configuration:
    Uses config.json or environment variables (same as the MCP server).
    See README.md for configuration details.
"""

import asyncio
import csv
import logging
from datetime import datetime
from pathlib import Path
from src.config import Config
from src.agiloft_client import AgiloftClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def export_contracts_to_csv(output_file: str = None):
    """
    Export all contracts from Agiloft to a CSV file.

    Args:
        output_file: Path to output CSV file. If None, generates a timestamped filename.

    Returns:
        str: Path to the created CSV file
    """
    # Generate default filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"agiloft_contracts_{timestamp}.csv"

    logger.info("Starting Agiloft contract export...")

    # Load configuration
    try:
        config = Config()
        if not config.validate():
            logger.error("Configuration validation failed. Please check your config.json or environment variables.")
            logger.error("Required: agiloft.base_url, agiloft.username, agiloft.password, agiloft.kb")
            return None
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return None

    # Connect to Agiloft and retrieve contracts
    async with AgiloftClient(config) as client:
        try:
            logger.info("Authenticating with Agiloft...")
            await client.ensure_authenticated()
            logger.info("Authentication successful!")

            logger.info("Retrieving all contracts...")
            # Search with no query to get all contracts
            # Specify common fields, but the API may return more
            contracts = await client.search_contracts(
                query="",
                fields=[
                    "id", "record_type", "contract_title1", "company_name",
                    "date_created", "date_submitted", "date_signed",
                    "contract_amount", "contract_end_date",
                    "contract_term_in_months", "internal_contract_owner",
                    "contract_description", "contract_status"
                ]
            )

            if not contracts:
                logger.warning("No contracts found in Agiloft.")
                return None

            logger.info(f"Retrieved {len(contracts)} contracts")

            # Determine all unique fields across all contracts
            all_fields = set()
            for contract in contracts:
                all_fields.update(contract.keys())

            # Sort fields for consistent column order (id first, then alphabetical)
            sorted_fields = sorted(all_fields)
            if 'id' in sorted_fields:
                sorted_fields.remove('id')
                sorted_fields.insert(0, 'id')

            logger.info(f"Writing {len(contracts)} contracts to {output_file}...")
            logger.info(f"Fields: {', '.join(sorted_fields)}")

            # Write to CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=sorted_fields, extrasaction='ignore')

                # Write header
                writer.writeheader()

                # Write all contracts
                for contract in contracts:
                    # Convert any non-string values to strings for CSV
                    row = {}
                    for field in sorted_fields:
                        value = contract.get(field, '')
                        # Handle None values
                        if value is None:
                            row[field] = ''
                        # Handle lists and dicts by converting to string
                        elif isinstance(value, (list, dict)):
                            row[field] = str(value)
                        else:
                            row[field] = value

                    writer.writerow(row)

            logger.info(f"✅ Successfully exported {len(contracts)} contracts to {output_file}")

            # Show file size
            file_size = Path(output_file).stat().st_size
            if file_size < 1024:
                size_str = f"{file_size} bytes"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.2f} KB"
            else:
                size_str = f"{file_size / (1024 * 1024):.2f} MB"

            logger.info(f"File size: {size_str}")

            return output_file

        except Exception as e:
            logger.error(f"Failed to export contracts: {e}")
            return None


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Agiloft Contract Export to CSV")
    print("=" * 60)
    print()

    # You can customize the output filename here
    output_file = None  # Will auto-generate timestamped filename
    # Or specify a custom filename:
    # output_file = "my_contracts.csv"

    result = await export_contracts_to_csv(output_file)

    if result:
        print()
        print("=" * 60)
        print(f"✅ Export completed successfully!")
        print(f"📄 Output file: {result}")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ Export failed. Check the logs above for details.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
