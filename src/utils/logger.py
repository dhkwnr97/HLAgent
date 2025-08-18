"""
Logging configuration for HLAgent
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


def setup_logger(name: str, log_level: str = "INFO", 
                log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up logger with console and file handlers, automatically saving to data/logs folder.
    
    Args:
        name: Logger name
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path (if None, creates default in data/logs)
        
    Returns:
        Configured logger
    """
    # Create logger
    logger = logging.getLogger(name)
    
    # Don't add handlers if already configured
    if logger.handlers:
        return logger
    
    # Set level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler - always create one in data/logs
    if not log_file:
        # Create default log file in data/logs based on module name
        timestamp = datetime.now().strftime("%Y%m%d")
        module_name = name.replace("src.", "").replace(".", "_")
        log_file = f"data/logs/hlagent_{module_name}_{timestamp}.log"
    
    # Ensure log file path is relative to project root
    if not log_file.startswith("data/logs"):
        log_file = f"data/logs/{Path(log_file).name}"
    
    # Create log directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Prevent propagation to parent loggers
    logger.propagate = False
    
    return logger


class HLAgentLogger:
    """
    Centralized logger for HLAgent with different log categories.
    All logs are automatically saved to data/logs folder.
    """
    
    def __init__(self, log_dir: Optional[str] = None, log_level: str = "INFO"):
        self.log_dir = Path(log_dir) if log_dir else Path("data/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_level = log_level
        
        # Create timestamp for session
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize loggers with data/logs path
        self.main_logger = self._create_logger("main", "hlagent_main.log")
        self.agent_logger = self._create_logger("agents", "hlagent_agents.log")
        self.tool_logger = self._create_logger("tools", "hlagent_tools.log")
        self.error_logger = self._create_logger("errors", "hlagent_errors.log")
        self.analysis_logger = self._create_logger("analysis", "hlagent_analysis.log")
    
    def _create_logger(self, name: str, filename: str) -> logging.Logger:
        """Create logger with specific configuration in data/logs folder"""
        log_file = self.log_dir / f"{self.session_id}_{filename}"
        return setup_logger(f"hlagent.{name}", self.log_level, str(log_file))
    
    def get_logger(self, category: str) -> logging.Logger:
        """Get logger by category"""
        loggers = {
            "main": self.main_logger,
            "agents": self.agent_logger, 
            "tools": self.tool_logger,
            "errors": self.error_logger,
            "analysis": self.analysis_logger
        }
        return loggers.get(category, self.main_logger)
    
    def log_workflow_start(self, workflow_name: str, parameters: dict):
        """Log workflow start"""
        self.main_logger.info(f"Starting workflow: {workflow_name}")
        self.main_logger.info(f"Parameters: {parameters}")
    
    def log_workflow_end(self, workflow_name: str, success: bool, duration: float):
        """Log workflow completion"""
        status = "SUCCESS" if success else "FAILED"
        self.main_logger.info(f"Workflow {workflow_name} completed: {status} (Duration: {duration:.2f}s)")
    
    def log_agent_action(self, agent_name: str, action: str, details: dict = None):
        """Log agent action"""
        self.agent_logger.info(f"Agent {agent_name}: {action}")
        if details:
            self.agent_logger.debug(f"Details: {details}")
    
    def log_tool_execution(self, tool_name: str, command: str, success: bool, duration: float = None):
        """Log tool execution"""
        status = "SUCCESS" if success else "FAILED"
        log_msg = f"Tool {tool_name}: {command} - {status}"
        if duration:
            log_msg += f" (Duration: {duration:.2f}s)"
        self.tool_logger.info(log_msg)
    
    def log_error(self, error_type: str, error_message: str, context: dict = None):
        """Log error with context"""
        self.error_logger.error(f"Error type: {error_type}")
        self.error_logger.error(f"Message: {error_message}")
        if context:
            self.error_logger.error(f"Context: {context}")
    
    def log_analysis_step(self, step_name: str, input_files: list, output_files: list, parameters: dict = None):
        """Log analysis step"""
        self.analysis_logger.info(f"Analysis step: {step_name}")
        self.analysis_logger.info(f"Input files: {input_files}")
        self.analysis_logger.info(f"Output files: {output_files}")
        if parameters:
            self.analysis_logger.debug(f"Parameters: {parameters}")


# Backward compatibility function
def get_logger(name: str, log_level: str = "INFO") -> logging.Logger:
    """
    Backward compatibility function - redirects to setup_logger.
    
    Args:
        name: Logger name
        log_level: Logging level
        
    Returns:
        Configured logger
    """
    return setup_logger(name, log_level)
