"""
Main entry point for Genotype Phasing Agent.
"""

import asyncio
import sys
from .agent import GenotypePhasingAgent


async def main():
    """Main function for standalone execution."""
    agent = GenotypePhasingAgent()
    
    try:
        output_files = await agent.chat_loop()
        
        if output_files:
            print(f"\n📋 Final output files:")
            for file in output_files:
                print(f"  • {file}")
        
        print("\n👋 Goodbye!")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())