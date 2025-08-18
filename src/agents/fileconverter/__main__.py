"""
Main entry point for File Converter Agent.

Allows standalone execution with: python -m src.agents.fileconverter
"""

import asyncio
import sys
from .agent import FileConverterAgent


async def main():
    """Main function for standalone execution."""
    print("🔄 Starting Professional File Converter Agent...")
    
    agent = FileConverterAgent()
    
    try:
        output_files = await agent.chat_loop()
        
        if output_files:
            print(f"\n📋 Final output files:")
            for file in output_files:
                print(f"  • {file}")
        
        print("\n👋 Thank you for using File Converter Agent!")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())