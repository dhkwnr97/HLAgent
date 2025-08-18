"""
Standalone execution entry point for New Parameter Handler Agent.

Usage:
    python -m src.agents.Newparameterhandler.agent [yaml_file_path]
"""

import sys
import asyncio
import os
from pathlib import Path

from .agent import NewParameterHandlerAgent


def print_banner():
    """Print the application banner."""
    print("=" * 70)
    print("           New Parameter Handler Agent")
    print("=" * 70)
    print("🔧 Professional YAML Parameter File Modifier")
    print("   for Bioinformatics Workflows")
    print("=" * 70)
    print()


def print_usage():
    """Print usage information."""
    print("Usage:")
    print("    python -m src.agents.Newparameterhandler [yaml_file_path]")
    print()
    print("Examples:")
    print("    # Interactive mode - will prompt for file path")
    print("    python -m src.agents.Newparameterhandler")
    print()
    print("    # Direct file mode")
    print("    python -m src.agents.Newparameterhandler /path/to/config_orig.yaml")
    print()
    print("Features:")
    print("    ✅ Interactive YAML parameter modification")
    print("    ✅ Line-by-line editing with validation")
    print("    ✅ Multiple modifications per command")
    print("    ✅ Real-time syntax validation")
    print("    ✅ Safe file handling with backup")
    print()


def get_yaml_file_path() -> str:
    """Get YAML file path from user input or command line arguments."""
    
    # Check command line arguments
    if len(sys.argv) > 1:
        yaml_path = sys.argv[1]
        if not os.path.exists(yaml_path):
            print(f"❌ Error: File not found: {yaml_path}")
            sys.exit(1)
        return yaml_path
    
    # Interactive mode - prompt for file path
    print("📁 Please enter the path to your YAML file:")
    print("   (It should be an _orig.yaml file for safety)")
    print()
    
    while True:
        try:
            yaml_path = input("YAML file path: ").strip()
            
            if not yaml_path:
                print("❌ Please enter a valid file path.")
                continue
            
            # Expand user home directory if needed
            yaml_path = os.path.expanduser(yaml_path)
            
            if not os.path.exists(yaml_path):
                print(f"❌ File not found: {yaml_path}")
                print("   Please check the path and try again.")
                continue
            
            if not yaml_path.endswith('.yaml'):
                print("⚠️  Warning: File doesn't have .yaml extension")
                confirm = input("Continue anyway? (y/n): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            
            return yaml_path
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            continue


async def main():
    """Main execution function."""
    try:
        print_banner()
        
        # Handle help requests
        if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
            print_usage()
            return
        
        # Get YAML file path
        yaml_path = get_yaml_file_path()
        
        print(f"🎯 Selected file: {yaml_path}")
        print()
        
        # Validate file
        if not yaml_path.endswith('_orig.yaml'):
            print("💡 Tip: For safety, it's recommended to use '_orig.yaml' files")
            print("   The agent will create a working copy for modifications.")
            print()
        
        # Create and run the agent
        agent = NewParameterHandlerAgent()
        
        print("🚀 Starting interactive session...")
        print("   Type 'help' for available commands")
        print("   Type 'Done!' when you're finished")
        print("   Press Ctrl+C to exit")
        print()
        
        # Run the chat loop
        result = await agent.chat_loop(yaml_path)
        
        # Display final result
        print("\n" + "=" * 60)
        print("📊 Session Summary:")
        print(f"   Status: {result['status']}")
        
        if result['status'] == 'completed':
            print(f"   ✅ Working file: {result['working_file']}")
            print(f"   📄 Original file: {result['original_file']}")
            print("   🎉 All modifications saved successfully!")
        elif result['status'] == 'aborted':
            print("   ⚠️  Session was aborted")
        elif result['status'] == 'interrupted':
            print("   ⚠️  Session was interrupted")
        else:
            print(f"   ❌ Error: {result.get('message', 'Unknown error')}")
        
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n👋 Session interrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())