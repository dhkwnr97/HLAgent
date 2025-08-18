"""
Node3: Stepwise Conditional Regression from HLA Binary Marker Panel.

This node performs stepwise conditional regression analysis from HLA binary marker panels
to identify independent association signals by conditioning on previously identified associations.

This analysis helps identify multiple independent genetic signals within the HLA region.
"""

import os
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from src.core.workchain import create_workchain
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class Node3:
    """Stepwise Conditional Regression from HLA Binary Marker Panel Node."""
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.name = "node3"
        self.description = "Stepwise conditional regression from HLA binary marker panel"
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.output_files: List[str] = []
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Node3: Stepwise conditional regression from HLA binary marker panel.
        
        Args:
            state: Current agent state
            
        Returns:
            Execution result dictionary
        """
        try:
            logger.info("Starting Node3 execution: Stepwise conditional regression from HLA binary marker panel")
            
            # Clear previous output files
            self.output_files = []
            
            # Execute stepwise conditional regression
            logger.info("Executing stepwise conditional regression analysis")
            stepwise_result = await self._execute_bmarkerstepwiseregression_workchain()
            
            if stepwise_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": stepwise_result.get("error_message", "Stepwise regression workchain failed"),
                    "node_name": self.name
                }
            
            # Add stepwise regression output files
            self.output_files.extend(stepwise_result.get("output_files", []))
            
            # Inform user about completion
            output_files = stepwise_result.get('output_files', [])
            print(f"✅ Stepwise conditional regression completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            logger.info(f"Node3 execution completed successfully. Total output files: {len(self.output_files)}")
            
            return {
                "status": "completed",
                "output_files": self.output_files,
                "node_name": self.name,
                "message": f"Node3 completed successfully. Generated {len(self.output_files)} output files.",
                "execution_steps": [
                    "Stepwise conditional regression analysis"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in Node3 execution: {e}")
            return {
                "status": "error",
                "output_files": self.output_files,
                "error_message": str(e),
                "node_name": self.name
            }
    
    async def _execute_bmarkerstepwiseregression_workchain(self) -> Dict[str, Any]:
        """Execute Binary Marker Stepwise Regression workchain."""
        try:
            logger.info("Executing Binary Marker Stepwise Regression workchain")
            
            # Create workchain for Binary Marker Stepwise Regression
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/bmarkerstepwiseregression_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_bmarkerstepwiseregression.py"
                ),
                output_file_extensions=[".txt", ".json", ".csv"],
                output_file_prefixes=[]
            )
            
            if output_files:
                logger.info(f"Binary Marker Stepwise Regression workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Binary Marker Stepwise Regression completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Binary Marker Stepwise Regression workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Binary Marker Stepwise Regression workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Binary Marker Stepwise Regression workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Binary Marker Stepwise Regression workchain error: {str(e)}"
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get node information."""
        return {
            "name": self.name,
            "description": self.description,
            "output_files": self.output_files,
            "expected_outputs": [".txt", ".json", ".csv"],
            "execution_steps": [
                "Stepwise conditional regression analysis"
            ],
            "requirements": "Requires HLA binary marker panel from Node1 (.bed, .bim, .fam, .phe files)."
        }