import os
from dotenv import load_dotenv
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


load_dotenv()


class HLAHDRunner:
    """
    Manages and executes HLA-HD imputation using Docker.
    It automatically translates host paths from the config file to container paths.
    """

    def __init__(self, config_path: str = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/HLAimputation/hlahd/hlahd_run_config.yaml")):
        """
        Initializes the HLAHDRunner.

        Args:
            config_path: Path to the HLA-HD configuration YAML file.
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

    def _build_docker_command(self) -> List[str]:
        """Builds the `docker run` command from the configuration."""
        params = self.config.get("hlahd_params", {})
        
        command = [self.docker_runner.docker_cmd, "run", "--user", "root", "--rm"]
        
        # Volume mounts
        for mount in self.config.get("volume_mounts", []):
            host_path = Path(mount["host_path"]).resolve()
            container_path = mount["container_path"]
            command.extend(["-v", f"{host_path}:{container_path}"])
        
        # Working directory
        command.extend(["-w", "/opt/hlahd.1.7.0"])
        
        # Docker image
        command.append(self.config["docker_image"])
        
        # Build the bash command
        bash_command = "mkdir -p /data/Output_dir && ./bin/hlahd.sh"
        
        # Add optional parameters based on hlahd.sh options
        # -t: threads
        threads = params.get("threads")
        if threads:
            bash_command += f" -t {threads}"
        
        # -c: rate of cutting
        rate_of_cutting = params.get("rate_of_cutting")
        if rate_of_cutting is not None:
            bash_command += f" -c {rate_of_cutting}"
        
        # -m: minimum tag size
        minimum_tag_size = params.get("minimum_tag_size")
        if minimum_tag_size is not None:
            bash_command += f" -m {minimum_tag_size}"
        
        # -n: number of mismatch
        number_of_mismatch = params.get("number_of_mismatch")
        if number_of_mismatch is not None:
            bash_command += f" -n {number_of_mismatch}"
        
        # -f: frequency directory
        freq_dir = params.get("freq_dir", "freq_data/")
        bash_command += f" -f {freq_dir}"
        
        # -N: size of ambiguous character
        ambiguous_char_size = params.get("ambiguous_char_size")
        if ambiguous_char_size is not None:
            bash_command += f" -N {ambiguous_char_size}"
        
        # Add input FASTQ files (translated to container paths)
        input_r1 = params.get("input_r1_fastq")
        input_r2 = params.get("input_r2_fastq")
        
        if not input_r1 or not input_r2:
            raise ValueError("Both input_r1_fastq and input_r2_fastq must be specified in config.")
        
        container_r1 = self._translate_path_to_container(input_r1)
        container_r2 = self._translate_path_to_container(input_r2)
        
        bash_command += f" {container_r1} {container_r2}"
        
        # Add fixed parameters: HLA_gene.split.txt, dictionary/, sample_id, output_directory
        sample_id = params.get("sample_id", "sampleID")
        bash_command += f" HLA_gene.split.txt dictionary/ {sample_id} /data/Output_dir"
        
        # Complete command
        command.extend(["/bin/bash", "-c", bash_command])
        
        return command

    def run_imputation(self) -> str:
        """
        Runs the HLA-HD imputation.
        
        Returns:
            The path to the host output directory.
        """
        command = self._build_docker_command()
        try:
            logger.info("Starting HLA-HD imputation...")
            logger.debug(f"Docker command: {' '.join(command)}")
            
            result = self.docker_runner.run(command)
            logger.info("HLA-HD imputation completed successfully.")
            logger.debug(f"HLA-HD stdout:\n{result.stdout}")
            
            # Find the output mount to return the correct host output directory
            for mount in self.config.get("volume_mounts", []):
                if "/data/Output_dir" in mount.get("container_path", ""):
                    return mount.get("host_path")
            return "Output directory not found in mounts"
        except RuntimeError as e:
            logger.error(f"HLA-HD imputation failed: {e}")
            raise

if __name__ == "__main__":
    try:
        runner = HLAHDRunner()
        output_dir = runner.run_imputation()
        logger.info(f"HLA-HD imputation completed. Results saved to: {output_dir}")
    except Exception as e:
        logger.critical(f"Failed to run HLA-HD imputation: {e}")
        import sys
        sys.exit(1)
