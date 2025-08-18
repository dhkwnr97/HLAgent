"""
Main entry point for Supervisor Agent.
"""

import asyncio
import sys
from .agent import SupervisorAgent
from .agent_types import SupervisorConfig

# Import agents to register
from src.agents.hlateacher.agent import HLATeacherAgent
from src.agents.genotypephasing.agent import GenotypePhasingAgent
from src.agents.parameterhandler.agent import ParameterHandlerAgent
from src.agents.fileconverter.agent import FileConverterAgent
from src.agents.hlaimputation.agent import HLAImputationAgent
from src.agents.hlafinemapping.agent import HLAFineMappingAgent


async def main():
    """Main function for standalone execution."""
    try:
        # Create supervisor agent
        config = SupervisorConfig()
        supervisor = SupervisorAgent(config)
        
        # Register agents
        print("🔧 Registering agents...")
        
        # Register HLA Teacher Agent
        hlateacher = HLATeacherAgent()
        supervisor.register_agent("hlateacher", hlateacher)
        
        # Register Genotype Phasing Agent
        phasing_agent = GenotypePhasingAgent()
        supervisor.register_agent("genotypephasing", phasing_agent)
        
        # Register Parameter Handler Agent
        param_handler = ParameterHandlerAgent()
        supervisor.register_agent("parameterhandler", param_handler)
        
        # Register File Converter Agent
        fileconverter = FileConverterAgent()
        supervisor.register_agent("fileconverter", fileconverter)
        
        # Register HLA Imputation Agent
        hlaimputation = HLAImputationAgent()
        supervisor.register_agent("hlaimputation", hlaimputation)
        
        # Register HLA Fine Mapping Agent (callback will be injected during handoff)
        hla_fine_mapping = HLAFineMappingAgent()
        supervisor.register_agent("hlafinemapping", hla_fine_mapping)
        
        print(f"✅ Registered {len(supervisor.get_registered_agents())} agents")
        
        # Start chat loop
        result = await supervisor.chat_loop()
        
        print(f"\n📊 Session completed with status: {result.get('status', 'unknown')}")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())