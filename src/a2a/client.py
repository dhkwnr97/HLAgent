"""
HLAgent A2A Client Implementation

Interactive chat client for communicating with HLAgent A2A server.
for chatting with HLAgent and its sub-agents through A2A protocol.

Usage:
    python src/a2a/client.py
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
import uuid
from typing import Optional
from fasta2a.client import A2AClient
from fasta2a.schema import Message, TextPart

from src.utils.logger import setup_logger


logger = setup_logger(__name__)



class HLAgentA2AClient:
    """
    A2A Client for interacting with HLAgent multi-agent system.
    
    Provides an interactive chat loop that allows users to:
    1. Chat with the supervisor agent
    2. Request handover to specific sub-agents
    3. Continue chatting with delegated agents
    4. Return to supervisor agent
    5. Exit the session
    """
    
    def __init__(self, base_url: str = None):
        """Initialize the A2A client."""
        if base_url is None:
            host = os.getenv("A2A_HOST", "localhost")
            port = os.getenv("A2A_PORT", "8995")
            base_url = f"http://{host}:{port}"
        
        self.client = A2AClient(base_url=base_url)
        self.context_id = str(uuid.uuid4())
        self.current_agent = "supervisor"
        self.base_url = base_url
        
    async def send_message(self, user_input: str) -> Optional[str]:
        """
        Send a message to the HLAgent A2A server and get response.
        
        Args:
            user_input: User's message text
            
        Returns:
            Agent's response text or None if failed
        """
        try:
            # Construct message
            message = Message(
                role='user',
                kind='message', 
                message_id=str(uuid.uuid4()),
                context_id=self.context_id,
                parts=[TextPart(kind='text', text=user_input)]
            )
            
            logger.debug(f"Sending message to {self.current_agent}: {user_input}")
            
            # Send message and get task
            response = await self.client.send_message(message)
            task = response.get("result")
            
            if not task or not isinstance(task, dict):
                logger.error("Failed to retrieve task info from response")
                return None
                
            task_id = task.get("id")
            if not task_id:
                logger.error("No task ID returned from server")
                return None
                
            # Poll for completion
            return await self._poll_for_completion(task_id)
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return f"❌ Communication error: {str(e)}"
    
    async def _poll_for_completion(self, task_id: str) -> Optional[str]:
        """
        Poll the server for task completion and extract response.
        
        Args:
            task_id: The task ID to monitor
            
        Returns:
            The agent's response text or error message
        """
        sleep_time = 1
        max_sleep = 60
        
        for attempt in range(60):  # Poll up to 60 times
            try:
                task_response = await self.client.get_task(task_id)
                task_data = task_response.get("result", {})
                status = task_data.get("status", {}).get("state", "unknown")
                
                if status == "completed":
                    artifacts = task_data.get("artifacts", [])
                    if not artifacts:
                        return "⚠️ Task completed but no response received."
                    
                    # Extract text from artifacts
                    responses = []
                    for artifact in artifacts:
                        for part in artifact.get("parts", []):
                            if part.get("kind") == "text":
                                responses.append(part.get("text", ""))
                    
                    return "\n".join(responses) if responses else "⚠️ No text response received."
                    
                elif status in {"failed", "canceled", "rejected"}:
                    error_msg = task_data.get("status", {}).get("error", "Unknown error")
                    return f"❌ Task failed: {error_msg}"
                
                # Continue polling
                await asyncio.sleep(sleep_time)
                sleep_time = min(sleep_time * 2, max_sleep)
                
            except Exception as e:
                logger.error(f"Error polling task {task_id}: {e}")
                return f"❌ Error checking task status: {str(e)}"
        
        return "⏰ Timeout: Agent did not respond in time."
    
    def _update_current_agent(self, response: str):
        """
        Update current agent based on response content.
        This helps track which agent the user is currently talking to.
        """
        response_lower = response.lower()
        
        # Check for handover messages - more comprehensive detection
        if ("handover to hla teacher" in response_lower or 
            "hla teacher agent" in response_lower or
            "delegated your query" in response_lower or
            "ready for your questions about hla" in response_lower or
            "delegated your query \"" in response_lower or
            "i have delegated your query" in response_lower):
            self.current_agent = "hlateacher"
        elif ("handover to file converter" in response_lower or 
              "file converter agent" in response_lower):
            self.current_agent = "fileconverter"
        elif ("handover to genotype phasing" in response_lower or 
              "genotype phasing agent" in response_lower):
            self.current_agent = "genotypephasing"
        elif ("handover to hla imputation" in response_lower or 
              "hla imputation agent" in response_lower):
            self.current_agent = "hlaimputation"
        elif ("handover to hla fine mapping" in response_lower or 
              "hla fine mapping agent" in response_lower):
            self.current_agent = "hlafinemapping"
        elif ("handover to parameter handler" in response_lower or 
              "parameter handler agent" in response_lower):
            self.current_agent = "parameterhandler"
        elif ("back to supervisor" in response_lower or 
              "welcome back" in response_lower or
              "i am back" in response_lower or
              "you are back with me, the supervisor" in response_lower or
              "back with me, the supervisor" in response_lower):
            self.current_agent = "supervisor"
    
    async def start_chat_loop(self):
        """
        Start the interactive chat loop.
        Continues until user types 'A2Aexit'.
        """
        print("🤖 HLAgent A2A Client Started")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("Welcome to HLAgent! You are now connected to the supervisor agent.")
        print("You can ask to be transferred to specialized agents:")
        print("  • 'I want to see hla teacher agent' - for HLA education")
        print("  • 'I want to see file converter agent' - for file conversion")
        print("  • 'I want to see genotype phasing agent' - for phasing analysis")
        print("  • 'I want to see hla imputation agent' - for HLA imputation")
        print("  • 'I want to see hla fine mapping agent' - for fine mapping")
        print("  • 'Done!' - to return to supervisor agent")
        print("  • 'A2Aexit' - to exit A2A Client")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        
        while True:
            try:
                # Display current agent context
                agent_indicator = f"[{self.current_agent}]" if self.current_agent != "supervisor" else "[supervisor]"
                user_input = input(f"👤 You {agent_indicator}>> ").strip()
                
                if user_input.lower() == 'a2aexit':
                    print("🤖 HLAgent: Goodbye! Exiting A2A client.")
                    break
                
                if not user_input:
                    print("⚠️  Please enter a message.")
                    continue
                
                # Send message and get response
                print("🤖 HLAgent: Processing your request...")
                response = await self.send_message(user_input)
                
                if response:
                    # Update current agent tracking
                    self._update_current_agent(response)
                    print(f"🤖 HLAgent: {response}")
                else:
                    print("❌ Failed to get response from HLAgent.")
                
                print()  # Add blank line for readability
                
            except KeyboardInterrupt:
                print("\n\n🤖 HLAgent: Chat interrupted. Goodbye!")
                break
            except Exception as e:
                logger.error(f"Error in chat loop: {e}")
                print(f"❌ Unexpected error: {str(e)}")
                print("Continuing chat session...")

async def main():
    """Main entry point for the A2A client."""
    try:
        client = HLAgentA2AClient()
        await client.start_chat_loop()
    except Exception as e:
        logger.error(f"Failed to start A2A client: {e}")
        print(f"❌ Failed to start HLAgent A2A Client: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())