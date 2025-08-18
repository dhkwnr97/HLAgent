"""
Node4: Omnibus Test from HLA Binary Marker Panel.

This node performs omnibus test analysis from HLA binary marker panels.
The omnibus test requires genotype phasing, which is handled automatically
through supervisor handoff to the genotype phasing agent.

This analysis tests overall association across the HLA region.
"""

import os
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from src.core.workchain import create_workchain
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class Node4:
    """Omnibus Test from HLA Binary Marker Panel Node."""
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.name = "node4"
        self.description = "Omnibus test from HLA binary marker panel"
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.output_files: List[str] = []
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Node4: Omnibus test from HLA binary marker panel.
        
        Args:
            state: Current agent state
            
        Returns:
            Execution result dictionary
        """
        try:
            logger.info("Starting Node4 execution: Omnibus test from HLA binary marker panel")
            
            # Clear previous output files
            self.output_files = []
            
            # Step 1: Genotype phasing (if needed)
            logger.info("Step 1: Checking genotype phasing requirements")
            phasing_result = await self._handle_genotype_phasing()
            
            if phasing_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": phasing_result.get("error_message", "Genotype phasing failed"),
                    "node_name": self.name
                }
            
            # Inform user about required files
            print("📋 Node4 requires .aa, .phe, .fam files for omnibus test analysis.")
            
            # Step 2: Omnibus test
            logger.info("Step 2: Omnibus test analysis")
            omnibus_result = await self._execute_omnibustest_workchain()
            
            if omnibus_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": omnibus_result.get("error_message", "Omnibus test workchain failed"),
                    "node_name": self.name
                }
            
            # Add Omnibus test output files
            self.output_files.extend(omnibus_result.get("output_files", []))
            
            # Inform user about completion
            output_files = omnibus_result.get('output_files', [])
            print(f"✅ Omnibus test completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            # Step 3: Omnibus test Manhattan plot generation
            logger.info("Step 3: Omnibus test manhattan plot generation")
            omni_manhattanplot_result = await self._execute_omnibus_manhattanplot_workchain()
            
            if omni_manhattanplot_result["status"] == "error":
                return {
                    "status": "error",
                    "output_files": self.output_files,
                    "error_message": omni_manhattanplot_result.get("error_message", "Omnibus test manhattan plot workchain failed"),
                    "node_name": self.name
                }
            
            # Add omnibus test manhattan plot output files
            self.output_files.extend(omni_manhattanplot_result.get("output_files", []))
            
            # Inform user about completion
            output_files = omni_manhattanplot_result.get('output_files', [])
            print(f"✅ Omnibus test manhattan plot generation completed. Generated {len(output_files)} files.")
            for file_path in output_files:
                print(f"   📄 {file_path}")
            
            logger.info(f"Node4 execution completed successfully. Total output files: {len(self.output_files)}")
            
            return {
                "status": "completed",
                "output_files": self.output_files,
                "node_name": self.name,
                "message": f"Node4 completed successfully. Generated {len(self.output_files)} output files.",
                "execution_steps": [
                    "Genotype phasing (if required)",
                    "Omnibus test analysis",
                    "Omnibus test manhattan plot generation"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in Node4 execution: {e}")
            return {
                "status": "error",
                "output_files": self.output_files,
                "error_message": str(e),
                "node_name": self.name
            }
    
    async def _handle_genotype_phasing(self) -> Dict[str, Any]:
        """Handle genotype phasing requirement."""
        try:
            logger.info("Handling genotype phasing requirement for omnibus test")
            
            # Check if genotype phasing is needed
            if await self._check_genotype_phasing_files():
                logger.info("Genotype phasing files already exist, skipping phasing step")
                return {
                    "status": "completed",
                    "message": "Genotype phasing files already available"
                }
            
            # Genotype phasing is needed
            if self.supervisor_handoff_callback:
                print("🧬 Genotype phasing required for omnibus test. Requesting genotype phasing via supervisor agent...")
                
                # Handoff to genotype phasing agent
                try:
                    await self.supervisor_handoff_callback(
                        agent_name="genotypephasing",
                        task_description="Genotype phasing for omnibus test analysis",
                        context="Node4 requires genotype phasing for omnibus test"
                    )
                    
                    print("✅ Genotype phasing completed successfully.")
                    return {
                        "status": "completed",
                        "message": "Genotype phasing completed via supervisor handoff"
                    }
                    
                except Exception as e:
                    logger.error(f"Genotype phasing handoff failed: {e}")
                    return {
                        "status": "error",
                        "error_message": f"Genotype phasing handoff failed: {str(e)}"
                    }
            else:
                logger.warning("No supervisor handoff callback available for genotype phasing")
                return {
                    "status": "error",
                    "error_message": "Genotype phasing required but no supervisor handoff available"
                }
                
        except Exception as e:
            logger.error(f"Error handling genotype phasing: {e}")
            return {
                "status": "error",
                "error_message": f"Error handling genotype phasing: {str(e)}"
            }
    
    async def _check_genotype_phasing_files(self) -> bool:
        """Check if genotype phasing files exist."""
        try:
            from pathlib import Path
            
            output_dir = Path(os.getenv("HLAGENT_MAIN_DIRECTORY", ".")) / "data" / "output"
            
            # Check for typical genotype phasing output files
            phasing_patterns = [".bgl.phased", ".aa", ".markers"]
            
            for pattern in phasing_patterns:
                matching_files = list(output_dir.rglob(f"*{pattern}"))
                if matching_files:
                    logger.info(f"Found genotype phasing files with pattern {pattern}")
                    return True
            
            logger.info("No genotype phasing files found")
            return False
            
        except Exception as e:
            logger.error(f"Error checking genotype phasing files: {e}")
            return False
    
    async def _execute_omnibustest_workchain(self) -> Dict[str, Any]:
        """Execute Omnibus Test workchain."""
        try:
            logger.info("Executing Omnibus Test workchain")
            
            # Create workchain for Omnibus Test
            workchain = create_workchain(supervisor_handoff_callback=self.supervisor_handoff_callback)
            
            # Execute workchain
            output_files = await workchain.execute_workchain(
                yaml_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/omnibustest_run_config_orig.yaml"
                ),
                python_script_path=os.path.join(
                    os.getenv("HLAGENT_MAIN_DIRECTORY", "."),
                    "src/tools/HATK/Runners/run_omnibustest.py"
                ),
                output_file_extensions=[".omnibus"],
                output_file_prefixes=[]
            )
            
            if output_files:
                logger.info(f"Omnibus Test workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Omnibus Test completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Omnibus Test workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Omnibus Test workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Omnibus Test workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Omnibus Test workchain error: {str(e)}"
            }
    
    async def _execute_omnibus_manhattanplot_workchain(self) -> Dict[str, Any]:
        """Execute Omnibus Test Manhattan Plot workchain."""
        try:
            logger.info("Executing Omnibus Test Manhattan Plot workchain")
            
            # Create workchain for Omnibus Test Manhattan Plot
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
                logger.info(f"Omnibus Test Manhattan Plot workchain completed successfully. Generated {len(output_files)} files.")
                return {
                    "status": "completed",
                    "output_files": output_files,
                    "message": f"Omnibus Test Manhattan Plot completed. Generated {len(output_files)} files."
                }
            else:
                logger.error("Omnibus Test Manhattan Plot workchain failed - no output files generated")
                return {
                    "status": "error",
                    "output_files": [],
                    "error_message": "Omnibus Test Manhattan Plot workchain failed - no output files generated"
                }
                
        except Exception as e:
            logger.error(f"Error in Omnibus Test Manhattan Plot workchain: {e}")
            return {
                "status": "error",
                "output_files": [],
                "error_message": f"Omnibus Test Manhattan Plot workchain error: {str(e)}"
            }
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get node information."""
        return {
            "name": self.name,
            "description": self.description,
            "output_files": self.output_files,
            "expected_outputs": [".omnibus", ".html", ".png", ".pdf", ".svg"],
            "execution_steps": [
                "Genotype phasing (if required)",
                "Omnibus test analysis",
                "Omnibus Test Manhattan Plot generation"
            ],
            "requirements": "Requires HLA binary marker panel from Node1 and genotype phasing (.aa, .phe, .fam files)."
        }