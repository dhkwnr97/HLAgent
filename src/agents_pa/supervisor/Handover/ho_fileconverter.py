"""
File Converter handover module for supervisor agent delegation.
Handles all File Converter agent handover operations for genotype and HLA file conversion.
"""

from src.agents_pa.supervisor.dependencies import SupervisorDependencies
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class FileConverterHandover:
    @staticmethod
    async def handover_to_fileconverter(
        initial_query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Hand over control to File Converter agent for interactive file conversion session.
        
        Args:
            initial_query: The file conversion query that triggered handover
            deps: Supervisor dependencies
            
        Returns:
            Summary of the handover session
        """
        try:
            from src.agents_pa.fileconverter.agent import fileconverter_agent_pa
            from src.agents_pa.fileconverter.dependencies import FileConverterDependencies
            
            # Start handover tracking
            deps.start_delegation("fileconverter", f"File conversion handover for: {initial_query[:50]}...")
            
            # Create File Converter dependencies with supervisor context
            fileconverter_deps = FileConverterDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Initialize file converter if needed
            await fileconverter_agent_pa.initialize(fileconverter_deps)
            
            # Display handover message
            print(f"\n Supervisor: I'll connect you with our File Converter specialist for file format conversion.")
            print(f"Initial request: {initial_query}")
            print("You can perform multiple file conversions. Type 'Done!' when finished.\n")
            
            # Start with the initial query to File Converter
            print("File Converter: Let me help you convert those files...")
            initial_response = await fileconverter_agent_pa.run(initial_query, fileconverter_deps)
            print(f"File Converter: {initial_response}\n")
            
            # Hand over control to File Converter for interactive session
            session_result = await fileconverter_agent_pa.chat_loop(
                deps=fileconverter_deps,
                standalone=False
            )
            
            # End handover
            deps.end_delegation()
            
            # Return summary
            session_summary = f"Completed interactive file conversion session with File Converter. Conversions completed: {session_result.get('conversions_completed', 0)}. Output files: {len(session_result.get('output_files', []))}. Session status: {session_result.get('status', 'unknown')}"
            
            logger.info(f"File Converter handover completed: {session_summary}")
            return session_summary
            
        except Exception as e:
            logger.error(f"Error in File Converter handover: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the File Converter: {str(e)}. Please try asking your question directly."
    
    @staticmethod
    async def process_with_fileconverter(
        query: str, 
        deps: SupervisorDependencies
    ) -> str:
        """
        Process query with File Converter agent (Streamlit-compatible).
        
        Args:
            query: The file conversion query
            deps: Supervisor dependencies
            
        Returns:
            Welcome message from File Converter instead of processing the initial query
        """
        try:
            from src.agents_pa.fileconverter.agent import fileconverter_agent_pa
            from src.agents_pa.fileconverter.dependencies import FileConverterDependencies
            
            # Start handover tracking
            deps.start_delegation("fileconverter", f"File conversion handover initiated: {query[:30]}...")
            
            # Create File Converter dependencies with supervisor context
            fileconverter_deps = FileConverterDependencies.create_default(
                session_id=deps.session_id,
                requester_agent="supervisor",
                task_id=f"handover_{len(deps.conversation_history)}"
            )
            
            # Store dependencies in supervisor for persistence
            deps.fileconverter_deps = fileconverter_deps
            
            # Initialize file converter if needed
            await fileconverter_agent_pa.initialize(fileconverter_deps)
            
            # Store the initial query for potential later use
            deps.add_conversation("user", query, "handover_trigger")
            
            # Return welcome message instead of processing the query
            welcome_response = f" **File Converter**: Hello! I'm the File Converter agent, specialized in genotype file format conversion and HLA imputation output processing.\n\n> **My capabilities**:\n\n**Category 1: Genotype File Conversion**\n- Convert various formats to PLINK binary (.bed, .bim, .fam)\n- Supported inputs: .gen/.sample, .bgen/.sample, .tped/.tfam, .ped/.map, .pgen/.pvar/.psam, .vcf, .vcf.gz, .bcf\n- Function 1: Standard conversion (uses workchain_pa)\n- Function 2: Beagle v3 to VCF (uses beagle2vcf.jar)\n- Function 3: VCF to Beagle v3 (uses vcf2beagle.jar)\n\n**Category 2: HLA Imputation Output Conversion**\n- Convert tool outputs to .hped format\n- Supported tools: AXIOM, HIBAG, XHLA, HLAHD, OPTITYPE\n\n *Tell me what type of conversion you need: 'genotype converting' or 'imputation converting'. Type 'Done!' when finished to return to the Supervisor.*"
            
            logger.info("Successfully initiated handover to File Converter with welcome message")
            return welcome_response
            
        except Exception as e:
            logger.error(f"Error initiating handover to File Converter: {e}")
            deps.end_delegation()
            return f"I encountered an error while connecting you with the File Converter: {str(e)}. Please try asking your question directly."
    
    @staticmethod
    async def process_fileconverter_followup(
        query: str,
        deps: SupervisorDependencies
    ) -> str:
        """
        Process follow-up query with File Converter (when already in handover mode).
        
        Args:
            query: Follow-up query for File Converter
            deps: Supervisor dependencies
            
        Returns:
            Response from File Converter
        """
        try:
            from src.agents_pa.fileconverter.agent import fileconverter_agent_pa
            from src.agents_pa.fileconverter.dependencies import FileConverterDependencies
            
            # Check if "Done!" to end handover
            if query.lower().strip() == "done!":
                deps.end_delegation()
                return "**Supervisor**: Welcome back! The File Converter session is complete. What can I do for you now?"
            
            # Reuse existing File Converter dependencies to preserve session state
            fileconverter_deps = deps.fileconverter_deps
            
            # If no existing deps, create new ones (fallback)
            if fileconverter_deps is None:
                fileconverter_deps = FileConverterDependencies.create_default(
                    session_id=deps.session_id,
                    requester_agent="supervisor",
                    task_id=f"followup_{len(deps.conversation_history)}"
                )
                deps.fileconverter_deps = fileconverter_deps
            
            await fileconverter_agent_pa.initialize(fileconverter_deps)
            response = await fileconverter_agent_pa.run(query, fileconverter_deps)
            
            # Add to conversation history
            deps.add_conversation("user", query, "fileconverter_session")
            deps.add_conversation("assistant", response, "fileconverter")
            
            return f"**File Converter**: {response}\n\n*Continue with file conversions, or type 'Done!' to return to Supervisor.*"
            
        except Exception as e:
            logger.error(f"Error in File Converter follow-up: {e}")
            return f"**File Converter**: I encountered an error: {str(e)}. Type 'Done!' to return to Supervisor."