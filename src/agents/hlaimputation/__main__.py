"""
Entry point for HLA Imputation Agent.

Allows the agent to be run as a module with:
python -m src.agents.hlaimputation
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parents[3]
sys.path.insert(0, str(project_root))

from .agent import HLAImputationAgent
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def main():
    """Main entry point for standalone execution."""
    try:
        print("🧬 Starting HLA Imputation Agent...")
        
        # Create agent instance (no supervisor callback for standalone)
        agent = HLAImputationAgent()
        
        # Run in interactive mode
        result = await agent.chat_loop()
        
        # Print final summary
        print(f"\n{'='*50}")
        print("📊 FINAL SUMMARY:")
        print(f"Status: {result['status']}")
        print(f"Output files: {result['file_count']}")
        
        if result.get('output_files'):
            print("Generated files:")
            for file_path in result['output_files']:
                print(f"  • {file_path}")
        
        return result
        
    except KeyboardInterrupt:
        print("\n\n🛑 Agent stopped by user.")
        return {"status": "interrupted"}
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"❌ Error: {e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    # Run the agent
    result = asyncio.run(main())
    
    # Exit with appropriate code
    if result["status"] == "completed":
        sys.exit(0)
    else:
        sys.exit(1)