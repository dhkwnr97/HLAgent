"""
Node2: Regression Analysis from HLA Binary Marker Panel.

This node performs regression analysis from HLA binary marker panels through workchains:
1. Binary marker regression - performs association analysis
2. Manhattan plot generation - creates visualization plots
3. Heatmap generation - creates heatmap visualizations

This node generates association results and comprehensive visualizations.
"""

import os
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from src.core.workchain import create_workchain
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class Node2:
    """Regression Analysis from HLA Binary Marker Panel Node."""
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.name = "node2"
        self.description = "Regression analysis from HLA binary marker panel"
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.output_files: List[str] = []
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Node2: Regression analysis from HLA binary marker panel.
        
        Args:
            state: Current agent state
            
        Returns:
            Execution result dictionary
        """
        try:
            logger.info("Starting Node2 execution: Regression analysis from HLA binary marker panel")
            
            # Clear previous output files
            self.output_files = []
            
            # Step 1: Binary marker regression
            logger.info("Step 1: Binary marker regression analysis")
            regression_result = await self._execute_bmarkerregression_workchain()
            
            if regression_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": regression_result.get("error_message", "Binary marker regression workchain failed"),
                    "node_name": self.name
                }
            
            # Add regression output files
            self.output_files.extend(regression_result.get("output_files", []))
            
            # Inform user about completion
            output_files = regression_result.get('output_files', [])
            print(f"✅ Binary marker regression completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            # Step 2: Manhattan plot generation
            logger.info("Step 2: Manhattan plot generation")
            manhattan_result = await self._execute_manhattanplot_workchain()
            
            if manhattan_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": manhattan_result.get("error_message", "Manhattan plot workchain failed"),
                    "node_name": self.name
                }
            
            # Add Manhattan plot output files
            self.output_files.extend(manhattan_result.get("output_files", []))
            
            # Inform user about completion
            output_files = manhattan_result.get('output_files', [])
            print(f"✅ Manhattan plot generation completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            # Step 3: Heatmap generation
            logger.info("Step 3: Heatmap generation")
            heatmap_result = await self._execute_heatmap_workchain()
            
            if heatmap_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": heatmap_result.get("error_message", "Heatmap workchain failed"),
                    "node_name": self.name
                }
            
            # Add heatmap output files
            self.output_files.extend(heatmap_result.get("output_files", []))
            
            # Inform user about completion
            output_files = heatmap_result.get('output_files', [])
            print(f"✅ Heatmap generation completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            logger.info(f"Node2 execution completed successfully. Total output files: {len(self.output_files)}")
            
            return {
                "status": "completed",
                "output_files": self.output_files,
                "node_name": self.name,
                "message": f"Node2 completed successfully. Generated {len(self.output_files)} output files.",
                "execution_steps": [
                    "Binary marker regression analysis",
                    "Manhattan plot generation",
                    "Heatmap generation"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in Node2 execution: {e}")
            return {
                "status": "error",
                "output_files": self.output_files,
                "error_message": str(e),
                "node_name": self.name
            }
    
    async def _execute_bmarkerregression_workchain(self) -> Dict[str, Any]:
        """Execute Binary Marker Regression workchain."""
        try:
            logger.info("Executing Binary Marker Regression workchain")
            
            # Create workchain for Binary Marker Regression
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/bmarkerregression_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_bmarkerregression.py"
                ),
                output_file_extensions=[".assoc.logistic", ".assoc.linear"],
                output_file_prefixes=[]
            )
            
            if output_files:
                logger.info(f"Binary Marker Regression workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Binary Marker Regression completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Binary Marker Regression workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Binary Marker Regression workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Binary Marker Regression workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Binary Marker Regression workchain error: {str(e)}"
            }
    
    async def _execute_manhattanplot_workchain(self) -> Dict[str, Any]:
        """Execute Manhattan Plot workchain."""
        try:
            logger.info("Executing Manhattan Plot workchain")
            
            # Create workchain for Manhattan Plot
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/manhattanPlot_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_manhattanPlot.py"
                ),
                output_file_extensions=[".html", ".png", ".pdf", ".svg"],
                output_file_prefixes=[]
            )
            
            if output_files:
                logger.info(f"Manhattan Plot workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Manhattan Plot completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Manhattan Plot workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Manhattan Plot workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Manhattan Plot workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Manhattan Plot workchain error: {str(e)}"
            }
    
    async def _execute_heatmap_workchain(self) -> Dict[str, Any]:
        """Execute Heatmap workchain."""
        try:
            logger.info("Executing Heatmap workchain")
            
            # Create workchain for Heatmap
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/heatmap_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_heatmap.py"
                ),
                output_file_extensions=[".html", ".png", ".pdf", ".svg"],
                output_file_prefixes=[]
            )
            
            if output_files:
                logger.info(f"Heatmap workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Heatmap completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Heatmap workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Heatmap workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Heatmap workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Heatmap workchain error: {str(e)}"
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get node information."""
        return {
            "name": self.name,
            "description": self.description,
            "output_files": self.output_files,
            "expected_outputs": [".assoc.logistic", ".assoc.linear", ".html", ".png", ".pdf", ".svg"],
            "execution_steps": [
                "Binary marker regression analysis",
                "Manhattan plot generation",
                "Heatmap generation"
            ],
            "requirements": "Requires HLA binary marker panel from Node1 (.bed, .bim, .fam, .phe files)."
        }