#!/usr/bin/env python3
"""
MCP Server Runner

This script properly sets up the Python path and runs the Agiloft MCP server.
Use this script in Claude Desktop configuration instead of calling src/server.py directly.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Change to project root directory so config.json can be found
os.chdir(project_root)

# Import and run the server
from src.server import main

if __name__ == "__main__":
    asyncio.run(main())