"""
Node5: Meta Analysis from Over 2 HLA Binary Marker Panels.

This node performs meta-analysis from multiple HLA binary marker panels.
It requires 2 or more .assoc.logistic or .assoc.linear files from Node2
runs on different phenotype datasets.

This analysis combines results across multiple datasets for more robust findings.
"""

import os
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from src.core.workchain import create_workchain
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


load_dotenv()


class Node5:
    """Meta Analysis from Over 2 HLA Binary Marker Panels Node."""
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.name = "node5"
        self.description = "Meta analysis from over 2 HLA binary marker panels"
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.output_files: List[str] = []
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Node5: Meta analysis from over 2 HLA binary marker panels.
        
        Args:
            state: Current agent state
            
        Returns:
            Execution result dictionary
        """
        try:
            logger.info("Starting Node5 execution: Meta analysis from over 2 HLA binary marker panels")
            
            # Clear previous output files
            self.output_files = []
            
            # Inform user about requirements
            print("📋 Node5 requires 2+ .assoc.logistic/.linear files from Node2 runs on different .phe datasets.")
            logger.info("Node5 requires 2+ association files for meta-analysis")
            
            # Step 1: Meta-analysis
            logger.info("Step 1: Meta-analysis")
            metaanal_result = await self._execute_metaanal_workchain()
            
            if metaanal_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": metaanal_result.get("error_message", "Meta-analysis workchain failed"),
                    "node_name": self.name
                }
            
            # Add meta-analysis output files
            self.output_files.extend(metaanal_result.get("output_files", []))
            
            # Inform user about completion
            output_files = metaanal_result.get('output_files', [])
            print(f"✅ Meta-analysis completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            # Step 2: Meta-analysis plot generation
            logger.info("Step 2: Meta-analysis plot generation")
            metaplot_result = await self._execute_metaanalplot_workchain()
            
            if metaplot_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": metaplot_result.get("error_message", "Meta-analysis plot workchain failed"),
                    "node_name": self.name
                }
            
            # Add meta-analysis plot output files
            self.output_files.extend(metaplot_result.get("output_files", []))
            
            # Inform user about completion
            output_files = metaplot_result.get('output_files', [])
            print(f"✅ Meta-analysis plot generation completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            logger.info(f"Node5 execution completed successfully. Total output files: {len(self.output_files)}")
            
            return {
                "status": "completed",
                "output_files": self.output_files,
                "node_name": self.name,
                "message": f"Node5 completed successfully. Generated {len(self.output_files)} output files.",
                "execution_steps": [
                    "Meta-analysis",
                    "Meta-analysis plot generation"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in Node5 execution: {e}")
            return {
                "status": "error",
                "output_files": self.output_files,
                "error_message": str(e),
                "node_name": self.name
            }
    
    async def _execute_metaanal_workchain(self) -> Dict[str, Any]:
        """Execute Meta-analysis workchain."""
        try:
            logger.info("Executing Meta-analysis workchain")
            
            # Create workchain for Meta-analysis
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/metaanal_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_metaanal.py"
                ),
                output_file_extensions=[".meta", "_summary.txt"],
                output_file_prefixes=[]
            )
            
            if output_files:
                logger.info(f"Meta-analysis workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Meta-analysis completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Meta-analysis workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Meta-analysis workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Meta-analysis workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Meta-analysis workchain error: {str(e)}"
            }
    
    async def _execute_metaanalplot_workchain(self) -> Dict[str, Any]:
        """Execute Meta-analysis Plot workchain."""
        try:
            logger.info("Executing Meta-analysis Plot workchain")
            
            # Create workchain for Meta-analysis Plot
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/metaanalPlot_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_metaanalPlot.py"
                ),
                output_file_extensions=[".png"],
                output_file_prefixes=[]
            )
            
            if output_files:
                logger.info(f"Meta-analysis Plot workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Meta-analysis Plot completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Meta-analysis Plot workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Meta-analysis Plot workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Meta-analysis Plot workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Meta-analysis Plot workchain error: {str(e)}"
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get node information."""
        return {
            "name": self.name,
            "description": self.description,
            "output_files": self.output_files,
            "expected_outputs": [".meta", "_summary.txt", ".png"],
            "execution_steps": [
                "Meta-analysis",
                "Meta-analysis plot generation"
            ],
            "requirements": "Requires 2+ .assoc.logistic/.linear files from Node2 runs on different .phe datasets."
        }