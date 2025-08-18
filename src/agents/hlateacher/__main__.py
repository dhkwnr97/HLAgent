import asyncio
from .agent import HLATeacherAgent

if __name__ == "__main__":
    agent = HLATeacherAgent()
    try:
        asyncio.run(agent.chat_loop())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Clean up resources
        try:
            asyncio.run(agent.cleanup())
        except Exception as e:
            print(f"Error during cleanup: {e}")