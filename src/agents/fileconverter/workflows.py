"""
Modular Workflow Classes for File Converter Agent.

Clean separation of genotype and imputation conversion workflows.
"""

import asyncio
from typing import List, Optional
from .tools import FileConverterTools
from .prompts import FILECONVERTER_PROMPTS
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


class BaseWorkflow:
    """Base class for conversion workflows."""
    
    def __init__(self, tools: FileConverterTools):
        self.tools = tools
    
    async def _get_user_input(self, prompt: str = "Your choice: ") -> str:
        """Get user input (async wrapper for input())."""
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: input(prompt).strip()
        )


class GenotypeWorkflow(BaseWorkflow):
    """Genotype conversion workflow with 3 modular functions."""
    
    def __init__(self, tools: 'FileConverterTools', agent=None):
        super().__init__(tools)
        self.agent = agent  # Reference to main agent for react_agent access
    
    async def execute(self) -> List[str]:
        """Execute genotype conversion workflow."""
        logger.info("Starting genotype conversion workflow")
        
        try:
            # Show welcome message
            print(FILECONVERTER_PROMPTS["genotype_welcome"])
            
            # Get user's natural language request
            user_request = await self._get_user_input("Describe your conversion needs: ")
            
            # Use LLM for intelligent analysis via react_agent
            if self.agent and hasattr(self.agent, 'react_agent'):
                analysis_result = await self._llm_analyze_request(user_request)
                if analysis_result:
                    return analysis_result
            
            # Fallback to simple keyword analysis
            function_number = self.tools.analyze_genotype_request(user_request)
            
            if function_number:
                # Confirm function with user
                if await self._confirm_function(function_number):
                    return await self._execute_function(function_number)
                
            # Show manual function selection
            return await self._manual_function_selection()
            
        except KeyboardInterrupt:
            print("\n🛑 Genotype conversion cancelled by user.")
            return []
        except Exception as e:
            logger.error(f"Genotype workflow error: {e}")
            print(f"❌ Error in genotype conversion: {e}")
            print("Please try again or contact support if the problem persists.")
            return []
    
    async def _llm_analyze_request(self, user_request: str) -> List[str]:
        """Use react_agent to analyze user request intelligently."""
        try:
            # Create enhanced prompt for LLM analysis
            analysis_prompt = FILECONVERTER_PROMPTS["llm_analysis_prompt"].format(user_request=user_request)
            
            # Use react_agent to process the request
            response = await self.agent.react_agent.ainvoke({"messages": [analysis_prompt]})
            
            # Extract response content
            response_content = ""
            if hasattr(response, 'content'):
                response_content = response.content.lower()
            elif isinstance(response, dict) and 'messages' in response:
                messages = response['messages']
                if messages and hasattr(messages[-1], 'content'):
                    response_content = messages[-1].content.lower()
            
            # Check if the response indicates a specific function to execute
            if "function 1" in response_content:
                print("🤖 LLM Analysis: Detected need for Function 1 (Various formats to PLINK binary)")
                return await self._execute_function(1)
            elif "function 2" in response_content:
                print("🤖 LLM Analysis: Detected need for Function 2 (Beagle v3 to VCF)")
                return await self._execute_function(2)
            elif "function 3" in response_content:
                print("🤖 LLM Analysis: Detected need for Function 3 (VCF to Beagle v3)")
                return await self._execute_function(3)
            
            # If LLM couldn't determine, fall back to manual selection
            print(f"🤖 LLM couldn't determine function automatically from: '{user_request}'")
            return None
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            print(f"⚠️ LLM analysis failed, falling back to manual selection: {e}")
            return None
    
    async def _confirm_function(self, function_number: int) -> bool:
        """Confirm function selection with user."""
        function_desc = FILECONVERTER_PROMPTS["function_descriptions"][str(function_number)]
        confirmation_msg = FILECONVERTER_PROMPTS["function_confirmation"].format(
            function_number=function_number,
            function_description=function_desc
        )
        print(confirmation_msg)
        
        confirmation = await self._get_user_input()
        return confirmation.lower() == "yes"
    
    async def _manual_function_selection(self) -> List[str]:
        """Manual function selection interface."""
        print(FILECONVERTER_PROMPTS["genotype_function_details"])
        
        function_choice = await self._get_user_input("Enter function number (1, 2, or 3): ")
        
        try:
            selected_function = int(function_choice.strip())
            if 1 <= selected_function <= 3:
                return await self._execute_function(selected_function)
            else:
                print("Invalid function number.")
                return []
        except ValueError:
            print("Invalid input. Please enter a number.")
            return []
    
    async def _execute_function(self, function_number: int) -> List[str]:
        """Execute the specified genotype function."""
        logger.info(f"Executing genotype function {function_number}")
        
        if function_number == 1:
            return await self._execute_function1()
        elif function_number == 2:
            return await self._execute_function2()
        elif function_number == 3:
            return await self._execute_function3()
        else:
            return []
    
    async def _execute_function1(self) -> List[str]:
        """Execute Function 1: Various formats to PLINK binary."""
        print(FILECONVERTER_PROMPTS["function1_workflow"])
        return await self.tools.execute_genotype_function1()
    
    async def _execute_function2(self) -> List[str]:
        """Execute Function 2: Beagle v3 to VCF."""
        print(FILECONVERTER_PROMPTS["function2_params"])
        params_input = await self._get_user_input("Parameters: ")
        
        params = self.tools.parse_function2_parameters(params_input)
        if not params:
            print("Invalid parameters format.")
            return []
        
        chrom, missing, output_filename = params
        
        markers_file = await self._get_user_input("Path to .markers file: ")
        bgl_file = await self._get_user_input("Path to .bgl file: ")
        
        return await self.tools.execute_genotype_function2(
            chrom, markers_file, bgl_file, missing, output_filename
        )
    
    async def _execute_function3(self) -> List[str]:
        """Execute Function 3: VCF to Beagle v3."""
        print(FILECONVERTER_PROMPTS["function3_params"])
        params_input = await self._get_user_input("Parameters: ")
        
        params = self.tools.parse_function3_parameters(params_input)
        if not params:
            print("Invalid parameters format.")
            return []
        
        missing, prefix = params
        vcf_file = await self._get_user_input("Path to VCF file: ")
        
        return await self.tools.execute_genotype_function3(
            vcf_file, missing, prefix
        )


class ImputationWorkflow(BaseWorkflow):
    """HLA imputation conversion workflow."""
    
    async def execute(self) -> List[str]:
        """Execute HLA imputation conversion workflow."""
        logger.info("Starting imputation conversion workflow")
        
        try:
            # Show welcome message
            print(FILECONVERTER_PROMPTS["imputation_welcome"])
            
            # Scan available tools
            available_tools = self.tools.scan_imputation_tools()
            
            if not available_tools:
                print("No HLA imputation conversion tools found.")
                return []
            
            # Show tool selection
            selected_tool = await self._select_tool(available_tools)
            
            if not selected_tool:
                print("No tool selected.")
                return []
            
            # Execute conversion
            return await self._execute_conversion(selected_tool)
            
        except KeyboardInterrupt:
            print("\\n🛑 HLA imputation conversion cancelled by user.")
            return []
        except Exception as e:
            logger.error(f"HLA imputation conversion workflow error: {e}")
            print(f"❌ Error in HLA imputation conversion: {e}")
            print("Please try again or contact support if the problem persists.")
            return []
    
    async def _select_tool(self, available_tools) -> Optional[object]:
        """Tool selection interface."""
        tool_list = self.tools.format_tool_list(available_tools)
        selection_msg = FILECONVERTER_PROMPTS["imputation_tool_selection"].format(
            tool_list=tool_list
        )
        print(selection_msg)
        
        tool_selection = await self._get_user_input("Select tool: ")
        
        return self.tools.find_tool_by_name_or_number(available_tools, tool_selection)
    
    async def _execute_conversion(self, selected_tool) -> List[str]:
        """Execute HLA conversion using workchain."""
        workflow_msg = FILECONVERTER_PROMPTS["imputation_workflow"].format(
            tool_name=selected_tool.display_name
        )
        print(workflow_msg)
        
        return await self.tools.execute_imputation_conversion(selected_tool)