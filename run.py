#!/usr/bin/env python3
"""
Quick start script for Sirex RWA Dashboard
"""

import asyncio
import sys
from pathlib import Path

# Check if .env exists
if not Path(".env").exists():
    print("⚠️  Warning: .env file not found!")
    print("📝 Copy .env.example to .env and add your API keys:")
    print("   cp .env.example .env")
    print()
    response = input("Continue anyway? (y/n): ")
    if response.lower() != 'y':
        sys.exit(0)

# Initialize database and fetch initial data
print("🔧 Initializing database...")
from app.data.cache import cache

async def init():
    await cache.init_db()
    print("✓ Database initialized")

asyncio.run(init())

# Start server
print("\n🚀 Starting Sirex RWA Dashboard...")
print("📊 Dashboard will be available at: http://localhost:8000")
print("⏹️  Press Ctrl+C to stop\n")

if __name__ == "__main__":
    import uvicorn
    # Disable reload on Windows to avoid multiprocessing issues
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
