"""
HLAgent A2A Server Implementation

Exposes the HLAgent supervisor agent as an A2A server for external communication.
This allows HLAgent to receive messages from A2A clients and provide responses
through the multi-agent system architecture.

Usage:
    uvicorn src.a2a.server:app --host 0.0.0.0 --port 8995
"""
import os
import sys
from dotenv import load_dotenv
from pathlib import Path
# Get the root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent
# Add the project root to the Python path
sys.path.append(str(ROOT_DIR))

import asyncio
import uvicorn

from src.agents_pa.supervisor.agent import supervisor_agent_pa, get_fresh_supervisor_agent
from src.utils.event_loop_fix import apply_event_loop_fix
from src.utils.logger import setup_logger

# Load environment variables
load_dotenv()

# Apply event loop fix for compatibility
apply_event_loop_fix()

logger = setup_logger(__name__)

# Global app variable
app = None

def main():
    """Main entry point for the A2A server."""
    global app
    logger.info("Starting HLAgent A2A Server...")
    
    # Create new event loop to prevent conflicts
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Setup the app
        loop.run_until_complete(_setup_app())
        
        # Start the server
        logger.info("A2A Server initialized, starting uvicorn...")
        port = int(os.getenv("A2A_PORT", "8995"))
        uvicorn.run(app, host="0.0.0.0", port=port, loop="asyncio")
    except Exception as e:
        logger.error(f"Failed to start A2A server: {e}")
        raise
    finally:
        loop.close()

async def _setup_app():
    """Setup the A2A application with proper initialization."""
    global app
    
    try:
        logger.info("Initializing supervisor agent...")
        
        # Initialize the supervisor agent if needed
        if hasattr(supervisor_agent_pa, 'initialize'):
            await supervisor_agent_pa.initialize()
        
        # Create fresh agent to avoid event loop issues
        fresh_agent = get_fresh_supervisor_agent()
        
        # Convert agent to A2A app
        host = os.getenv("A2A_HOST", "localhost")
        port = os.getenv("A2A_PORT", "8995")
        app = fresh_agent.to_a2a(
            name="HLAgent A2A Server",
            description="HLA multi-agent analysis system with A2A protocol support",
            version="1.0.0",
            url=f"http://{host}:{port}"
        )
        
        logger.info("HLAgent A2A Server setup complete")
        
    except Exception as e:
        logger.error(f"Failed to setup A2A app: {e}")
        raise

def get_app():
    """Get the A2A app instance (for direct ASGI usage)."""
    if app is None:
        asyncio.run(_setup_app())
    return app

if __name__ == "__main__":
    main()