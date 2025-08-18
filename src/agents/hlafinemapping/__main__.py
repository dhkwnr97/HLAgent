"""
Main entry point for HLA Fine Mapping Agent.

This module allows the agent to be run standalone using:
python -m src.agents.hlafinemapping
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import sys
import asyncio
 

# Add the project root to the Python path
project_root = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"))
sys.path.insert(0, project_root)

from src.agents.hlafinemapping.agent import HLAFineMappingAgent
from src.utils.logger import setup_logger

# Load environment variables
load_dotenv()


logger = setup_logger(__name__)


async def main():
    """Main entry point for standalone execution."""
    try:
        print("🧬 Initializing HLA Fine Mapping Agent...")
        
        # Create the agent instance (without supervisor callback for standalone mode)
        # Note: For standalone execution, workchain will run without parameter handler handoff
        agent = HLAFineMappingAgent(supervisor_handoff_callback=None)
        
        # Run the agent in standalone mode
        logger.info("Starting HLA Fine Mapping Agent in standalone mode")
        result = await agent.chat_loop()
        
        # Log final result
        logger.info(f"Agent execution completed with result: {result}")
        
        return result
        
    except KeyboardInterrupt:
        print("\n\n🛑 Agent execution interrupted by user.")
        logger.info("Agent execution interrupted by user")
        return {"status": "interrupted", "message": "Execution interrupted by user"}
        
    except Exception as e:
        print(f"\n❌ Error running HLA Fine Mapping Agent: {e}")
        logger.error(f"Error running agent: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Run the agent
    try:
        result = asyncio.run(main())
        
        # Exit with appropriate code
        if result.get("status") == "completed":
            sys.exit(0)
        elif result.get("status") == "interrupted":
            sys.exit(1)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Execution interrupted.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)