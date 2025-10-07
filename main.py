import asyncio
import os
from aiohttp import web

# Import components from other files
import account_manager
from web_server import create_app
from database import init_db
from config import API_ID, API_HASH

async def main():
    """Initializes the database, web server, and existing bot sessions."""

    # Initialize the database
    init_db()

    # Start clients for any existing session files
    await account_manager.start_existing_sessions(API_ID, API_HASH)

    # Create and run the web application
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    print("-" * 50)
    print("Web server running on http://0.0.0.0:8080")
    print("Open your browser and go to http://localhost:8080 to manage your accounts.")
    print("-" * 50)

    # Keep the application running forever
    await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested.")
