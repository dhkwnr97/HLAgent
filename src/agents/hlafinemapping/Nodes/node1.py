"""
Node1: HLA Binary Marker Panel Creation.

This node creates HLA binary marker panels through a series of workchains:
1. IMGT2SEQ conversion - converts IMGT reference to sequence format
2. Nomencleaner processing - cleans and standardizes nomenclature
3. Binary marker generation - creates binary marker panels

This is an essential node for users who haven't used HLA fine mapping before.
"""

import os
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from src.core.workchain import create_workchain
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class Node1:
    """HLA Binary Marker Panel Creation Node."""
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.name = "node1"
        self.description = "HLA binary marker panel creation"
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.output_files: List[str] = []
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Node1: HLA binary marker panel creation.
        
        Args:
            state: Current agent state
            
        Returns:
            Execution result dictionary
        """
        try:
            logger.info("Starting Node1 execution: HLA binary marker panel creation")
            
            # Clear previous output files
            self.output_files = []
            
            # Step 1: IMGT2SEQ conversion
            logger.info("Step 1: IMGT2SEQ conversion")
            imgt2seq_result = await self._execute_imgt2seq_workchain()
            
            if imgt2seq_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": imgt2seq_result.get("error_message", "IMGT2SEQ workchain failed"),
                    "node_name": self.name
                }
            
            # Add IMGT2SEQ output files
            self.output_files.extend(imgt2seq_result.get("output_files", []))
            
            # Inform user about completion
            output_files = imgt2seq_result.get('output_files', [])
            print(f"✅ IMGT2SEQ conversion completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            # Step 2: Nomencleaner processing
            logger.info("Step 2: Nomencleaner processing")
            nomencleaner_result = await self._execute_nomencleaner_workchain()
            
            if nomencleaner_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": nomencleaner_result.get("error_message", "Nomencleaner workchain failed"),
                    "node_name": self.name
                }
            
            # Add Nomencleaner output files
            self.output_files.extend(nomencleaner_result.get("output_files", []))
            
            # Inform user about completion
            output_files = nomencleaner_result.get('output_files', [])
            print(f"✅ Nomencleaner processing completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            # Step 3: Binary marker generation
            logger.info("Step 3: Binary marker generation")
            bmarker_result = await self._execute_bmarkergenerator_workchain()
            
            if bmarker_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": bmarker_result.get("error_message", "Binary marker generator workchain failed"),
                    "node_name": self.name
                }
            
            # Add Binary marker output files
            self.output_files.extend(bmarker_result.get("output_files", []))
            
            # Inform user about completion
            output_files = bmarker_result.get('output_files', [])
            print(f"✅ Binary marker generation completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            logger.info(f"Node1 execution completed. Total output files: {len(self.output_files)}")
            
            return {
                "status": "completed",
                "output_files": self.output_files,
                "node_name": self.name,
                "message": f"Node1 completed. Generated {len(self.output_files)} output files.",
                "execution_steps": [
                    "IMGT2SEQ conversion",
                    "Nomencleaner processing", 
                    "Binary marker generation"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in Node1 execution: {e}")
            return {
                "status": "error",
                "output_files": self.output_files,
                "error_message": str(e),
                "node_name": self.name
            }
    
    async def _execute_imgt2seq_workchain(self) -> Dict[str, Any]:
        """Execute IMGT2SEQ workchain."""
        try:
            logger.info("Executing IMGT2SEQ workchain")
            
            # Create workchain for IMGT2SEQ
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/imgt2seq_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_imgt2seq.py"
                ),
                output_file_extensions=[".hat"],
                output_file_prefixes=["HLA_DICTIONARY_AA", "HLA_DICTIONARY_SNPS"]
            )
            
            if output_files:
                logger.info(f"IMGT2SEQ workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"IMGT2SEQ completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("IMGT2SEQ workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "IMGT2SEQ workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in IMGT2SEQ workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"IMGT2SEQ workchain error: {str(e)}"
            }
    
    async def _execute_nomencleaner_workchain(self) -> Dict[str, Any]:
        """Execute Nomencleaner workchain."""
        try:
            logger.info("Executing Nomencleaner workchain")
            
            # Create workchain for Nomencleaner
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/nomencleaner_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_nomencleaner.py"
                ),
                output_file_extensions=[".chped"],
                output_file_prefixes=[]
            )
            
            if output_files:
                logger.info(f"Nomencleaner workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Nomencleaner completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Nomencleaner workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Nomencleaner workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Nomencleaner workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Nomencleaner workchain error: {str(e)}"
            }
    
    async def _execute_bmarkergenerator_workchain(self) -> Dict[str, Any]:
        """Execute Binary Marker Generator workchain."""
        try:
            logger.info("Executing Binary Marker Generator workchain")
            
            # Create workchain for Binary Marker Generator
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/bmarkergenerator_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_bmarkergenerator.py"
                ),
                output_file_extensions=[".bed", ".bim", ".fam"],
                output_file_prefixes=[]
            )
            
            if output_files:
                logger.info(f"Binary Marker Generator workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Binary Marker Generator completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Binary Marker Generator workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Binary Marker Generator workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Binary Marker Generator workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Binary Marker Generator workchain error: {str(e)}"
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get node information."""
        return {
            "name": self.name,
            "description": self.description,
            "output_files": self.output_files,
            "expected_outputs": [".hat", ".chped", ".bed", ".bim", ".fam"],
            "execution_steps": [
                "IMGT2SEQ conversion",
                "Nomencleaner processing",
                "Binary marker generation"
            ],
            "requirements": "Required .hped and .phe files. Essential for first-time users."
        }