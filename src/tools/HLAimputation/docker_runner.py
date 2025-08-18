"""
CookHLA Docker Integration for HLAgent
Provides interface to CookHLA Docker container
"""

import os
import logging
import subprocess
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
import shutil

from ...utils.logger import setup_logger

logger = setup_logger(__name__)

class DockerRunner:
    """A generic to run Docker commands."""

    def __init__(self, docker_cmd: str = "docker"):
        self.docker_cmd = self._find_docker_cmd(docker_cmd)
        self._check_docker_availability()

    def _find_docker_cmd(self, docker_cmd: str) -> str:
        """Find the docker executable."""
        from shutil import which
        if which(docker_cmd):
            return docker_cmd
        raise FileNotFoundError("Docker command not found in system's PATH.")

    def _check_docker_availability(self):
        """Check if Docker daemon is running."""
        try:
            subprocess.run(
                [self.docker_cmd, "info"],
                capture_output=True, text=True, check=True
            )
            logger.info("Docker is available and the daemon is running.")
        except FileNotFoundError:
            logger.error(f"The Docker command '{self.docker_cmd}' was not found.")
            raise RuntimeError("Docker is not installed or not in the system's PATH.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker daemon is not running or not accessible: {e.stderr}")
            raise RuntimeError("Docker daemon is not running. Please start Docker.")

    def image_exists(self, image_name: str) -> bool:
        """Check if a Docker image exists locally."""
        try:
            result = subprocess.run(
                [self.docker_cmd, "image", "inspect", image_name],
                capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking for image {image_name}: {e}")
            return False

    def pull_image(self, image_name: str, force: bool = False):
        """Pull a Docker image if it doesn't exist or if force is True."""
        if not force and self.image_exists(image_name):
            logger.info(f"Image '{image_name}' already exists. Skipping pull.")
            return

        logger.info(f"Pulling Docker image: {image_name}...")
        try:
            # Using PIPE to capture and log output in real-time could be an improvement
            result = subprocess.run(
                [self.docker_cmd, "pull", image_name],
                check=True, capture_output=True, text=True
            )
            logger.info(f"Successfully pulled image: {image_name}\n{result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to pull image '{image_name}': {e.stderr}")
            raise RuntimeError(f"Failed to pull Docker image '{image_name}'.")

    def run(self, command: List[str]) -> subprocess.CompletedProcess:
        """
        Run a command inside a Docker container.
        The command should be the full `docker run ...` command as a list of strings.
        """
        logger.info(f"Executing Docker command: {' '.join(command)}")
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True
            )
            logger.info(f"Docker command finished with return code {result.returncode}.")
            
            if result.stdout:
                logger.debug(f"stdout:\n{result.stdout}")
            if result.stderr:
                 logger.warning(f"stderr:\n{result.stderr}")
            
            result.check_returncode() # Raise CalledProcessError if return code is non-zero
            return result
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker command failed with return code {e.returncode}.")
            logger.error(f"Stderr: {e.stderr}")
            logger.error(f"Stdout: {e.stdout}")
            raise RuntimeError("Execution of Docker command failed.")
        except FileNotFoundError:
            logger.error(f"Docker command '{self.docker_cmd}' not found. Is Docker installed?")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while running docker command: {e}")
            raise