import os
from dotenv import load_dotenv
import logging
import yaml
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

# Add the project root directory to Python path
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)
    
from src.utils.logger import setup_logger
from src.tools.HLAimputation.docker_runner import DockerRunner


logger = setup_logger(__name__)


load_dotenv()


class OptiTypeRunner:
    """
    Manages and executes OptiType imputation using Docker.
    It automatically translates host paths from the config file to container paths.
    """

    def __init__(self, config_path: str = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/HLAimputation/optitype/optitype_run_config.yaml")):
        """
        Initializes the OptiTypeRunner.

        Args:
            config_path: Path to the OptiType configuration YAML file.
        """
        self.config = self._load_config(config_path)
        self.docker_runner = DockerRunner()
        self._prepare_environment()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Loads the YAML configuration file."""
        logger.info(f"Loading configuration from: {config_path}")
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found at {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise

    def _prepare_environment(self):
        """Prepares Docker image and host directories."""
        image_name = self.config.get("docker_image")
        if not image_name:
            raise ValueError("Docker image not specified in config.")
        
        logger.info("Preparing Docker environment...")
        self.docker_runner.pull_image(image_name)

        # Create host directories defined in mounts
        for mount in self.config.get("volume_mounts", []):
            if 'output' in mount.get('description', '').lower():
                host_path = Path(mount["host_path"])
                host_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Ensured host directory exists: {host_path}")

    def _translate_path_to_container(self, host_path: Optional[str]) -> Optional[str]:
        """Translates a host path to its corresponding container path based on volume mounts."""
        if not host_path:
            return None

        # Use Path for robust path manipulation
        abs_host_path = Path(host_path).resolve()

        for mount in self.config.get("volume_mounts", []):
            abs_mount_host_path = Path(mount["host_path"]).resolve()
            
            if abs_host_path.is_relative_to(abs_mount_host_path):
                # Get the relative path from the mount's host path
                relative_path = abs_host_path.relative_to(abs_mount_host_path)
                # Join with the container path
                container_path = Path(mount["container_path"]) / relative_path
                return str(container_path)

        raise ValueError(f"Path '{host_path}' is not within any configured volume mount.")

    def _create_config_file(self) -> str:
        """Creates a temporary config.ini file for OptiType."""
        config_content = self.config.get("optitype_params", {})
        
        config_ini_content = "[mapping]\n"
        mapping = config_content.get("mapping", {})
        config_ini_content += f"razers3={mapping.get('razers3', '/usr/local/bin/razers3')}\n"
        config_ini_content += f"threads={mapping.get('threads', 1)}\n\n"
        
        config_ini_content += "[ilp]\n"
        ilp = config_content.get("ilp", {})
        config_ini_content += f"solver={ilp.get('solver', 'cbc')}\n"
        config_ini_content += f"threads={ilp.get('threads', 1)}\n\n"
        
        config_ini_content += "[behavior]\n"
        behavior = config_content.get("behavior", {})
        config_ini_content += f"deletebam={str(behavior.get('deletebam', True)).lower()}\n"
        config_ini_content += f"unpaired_weight={behavior.get('unpaired_weight', 0)}\n"
        config_ini_content += f"use_discordant={str(behavior.get('use_discordant', False)).lower()}\n"
        
        # Create temporary config file
        temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False)
        temp_config.write(config_ini_content)
        temp_config.close()
        
        return temp_config.name

    def _build_docker_command(self) -> List[str]:
        """Builds the `docker run` command from the configuration."""
        params = self.config.get("optitype_params", {})
        
        command = [self.docker_runner.docker_cmd, "run", "--user", "root", "--rm"]
        
        # Volume mounts
        for mount in self.config.get("volume_mounts", []):
            host_path = Path(mount["host_path"]).resolve()
            container_path = mount["container_path"]
            command.extend(["-v", f"{host_path}:{container_path}"])
        
        # Create and mount config file
        config_file_path = self._create_config_file()
        command.extend(["-v", f"{config_file_path}:/opt/OptiType/config.ini"])
        
        # Add -t flag for pseudo-TTY
        command.append("-t")
        
        # Docker image
        command.append(self.config["docker_image"])
        
        # OptiType command arguments
        # Input files
        input_files = params.get("input_files", [])
        if not input_files:
            raise ValueError("input_files must be specified in config.")
        
        command.extend(["-i"])
        for input_file in input_files:
            container_path = self._translate_path_to_container(input_file)
            command.append(container_path)
        
        # Data type (required)
        data_type = params.get("data_type")
        if not data_type:
            raise ValueError("data_type must be specified in config (either 'rna' or 'dna').")
        
        if data_type.lower() == "rna":
            command.append("-r")
        elif data_type.lower() == "dna":
            command.append("-d")
        else:
            raise ValueError("data_type must be either 'rna' or 'dna'.")
        
        # Output directory
        output_dir = params.get("output_dir")
        if output_dir:
            container_output = self._translate_path_to_container(output_dir)
            command.extend(["-o", container_output])
        else:
            # Default to /output if not specified
            command.extend(["-o", "/output"])
        
        # Optional parameters
        beta = params.get("beta")
        if beta is not None:
            command.extend(["-b", str(beta)])
        
        enumerate = params.get("enumerate")
        if enumerate is not None and enumerate != 1:
            command.extend(["-e", str(enumerate)])
        
        if params.get("verbose", False):
            command.append("-v")
        
        # Config file
        command.extend(["-c", "/opt/OptiType/config.ini"])
        
        return command, config_file_path

    def run_imputation(self) -> str:
        """
        Runs the OptiType imputation.
        
        Returns:
            The path to the host output directory.
        """
        command, config_file_path = self._build_docker_command()
        try:
            logger.info("Starting OptiType imputation...")
            logger.debug(f"Docker command: {' '.join(command)}")
            
            result = self.docker_runner.run(command)
            logger.info("OptiType imputation completed successfully.")
            logger.debug(f"OptiType stdout:\n{result.stdout}")
            
            # Find the output mount to return the correct host output directory
            for mount in self.config.get("volume_mounts", []):
                if "output" in mount.get("description", "").lower():
                    return mount.get("host_path")
            return "Output directory not found in mounts"
        except RuntimeError as e:
            logger.error(f"OptiType imputation failed: {e}")
            raise
        finally:
            # Clean up temporary config file
            if os.path.exists(config_file_path):
                os.unlink(config_file_path)
                logger.debug(f"Cleaned up temporary config file: {config_file_path}")

if __name__ == "__main__":
    try:
        runner = OptiTypeRunner()
        output_dir = runner.run_imputation()
        logger.info(f"OptiType imputation completed. Results saved to: {output_dir}")
    except Exception as e:
        logger.critical(f"Failed to run OptiType imputation: {e}")
        import sys
        sys.exit(1) 