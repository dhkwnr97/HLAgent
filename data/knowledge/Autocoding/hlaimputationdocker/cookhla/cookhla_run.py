import logging
import yaml
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

class CookHLARunner:
    """
    Manages and executes CookHLA imputation using Docker.
    It automatically translates host paths from the config file to container paths.
    """

    def __init__(self, config_path: str = "src/tools/HLAimputation/cookhla/cookhla_run_config.yaml"):
        """
        Initializes the CookHLARunner.

        Args:
            config_path: Path to the CookHLA configuration YAML file.
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
            if 'output' in mount.get('description', ''):
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

    def _build_docker_command(self) -> List[str]:
        """Builds the `docker run` command from the configuration."""
        params = self.config.get("cookhla_params", {})
        
        command = [self.docker_runner.docker_cmd, "run", "--user", "root", "--rm"]
        
        # Volume mounts
        for mount in self.config.get("volume_mounts", []):
            host_path = Path(mount["host_path"]).resolve()
            container_path = mount["container_path"]
            command.extend(["-v", f"{host_path}:{container_path}"])
        
        command.append(self.config["docker_image"])
        command.append("CookHLA.py")
        
        # Translate paths and build arguments
        arg_map = {
            "input_prefix": "-i", "output_prefix": "-o", "reference_panel": "-ref",
            "genetic_map": "-gm", "error_rate": "-ae"
        }
        for key, flag in arg_map.items():
            host_path = params.get(key)
            if host_path:
                container_path = self._translate_path_to_container(host_path)
                command.extend([flag, container_path])

        # Non-path arguments
        static_arg_map = {"hg_version": "-hg", "memory": "-mem", "multiprocess": "-mp"}
        for key, flag in static_arg_map.items():
            if key in params:
                command.extend([flag, str(params[key])])

        if params.get("save_ambiguous_snp"):
            command.append("--save-Ambiguous-SNP")
            
        return command

    def run_imputation(self) -> str:
        """
        Runs the CookHLA imputation.
        
        Returns:
            The path to the host output directory.
        """
        command = self._build_docker_command()
        try:
            result = self.docker_runner.run(command)
            logger.info("CookHLA imputation completed successfully.")
            logger.debug(f"CookHLA stdout:\n{result.stdout}")
            # Find the output mount to return the correct host output directory
            for mount in self.config.get("volume_mounts", []):
                if mount.get("container_path") == "/output":
                    return mount.get("host_path")
            return "Output directory not found in mounts"
        except RuntimeError as e:
            logger.error(f"CookHLA imputation failed: {e}")
            raise

if __name__ == "__main__":
    try:
        runner = CookHLARunner()
        output_dir = runner.run_imputation()
        logger.info(f"CookHLA imputation completed. Results saved to: {output_dir}")
    except Exception as e:
        logger.critical(f"Failed to run CookHLA imputation: {e}")
        import sys
        sys.exit(1)
