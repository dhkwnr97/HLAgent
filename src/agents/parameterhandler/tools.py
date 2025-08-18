"""
Tools for Parameter Handler Agent.
"""

import os
import shutil
import yaml
from typing import List, Dict, Any, Tuple
from langchain_core.tools import tool

from .agent_types import YamlEditCommand


@tool
def copy_yaml_file(original_path: str) -> str:
    """
    Copy _orig.yaml file to working .yaml file, overwriting if exists.
    
    Args:
        original_path: Path to the original _orig.yaml file
        
    Returns:
        Path to the created working file
    """
    try:
        # Generate working file path by removing _orig suffix
        if original_path.endswith('_orig.yaml'):
            working_path = original_path.replace('_orig.yaml', '.yaml')
        else:
            working_path = original_path.replace('.yaml', '_working.yaml')
        
        # Copy file, overwriting if exists
        shutil.copy2(original_path, working_path)
        
        return f"Successfully copied {original_path} to {working_path}"
        
    except FileNotFoundError:
        return f"Error: Original file not found: {original_path}"
    except Exception as e:
        return f"Error copying file: {str(e)}"


@tool  
def read_yaml_with_line_numbers(yaml_path: str) -> str:
    """
    Read YAML file and return content with line numbers.
    
    Args:
        yaml_path: Path to the YAML file
        
    Returns:
        YAML content with line numbers
    """
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        numbered_content = []
        for i, line in enumerate(lines, 1):
            numbered_content.append(f"{i:3d}: {line.rstrip()}")
        
        return "\n".join(numbered_content)
        
    except FileNotFoundError:
        return f"Error: File not found: {yaml_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def modify_yaml_line(yaml_path: str, line_number: int, new_value: str) -> str:
    """
    Modify a specific line in a YAML file.
    
    Args:
        yaml_path: Path to the YAML file
        line_number: Line number to modify (1-based)
        new_value: New value to set
        
    Returns:
        Success or error message
    """
    try:
        # Read the file
        with open(yaml_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if line_number < 1 or line_number > len(lines):
            return f"Error: Line number {line_number} is out of range (file has {len(lines)} lines)"
        
        original_line = lines[line_number - 1].rstrip()
        
        # Check if the line contains a colon (YAML key-value pair)
        if ':' in original_line:
            # Split at the first colon and preserve indentation
            key_part, _ = original_line.split(':', 1)
            
            # Smart type handling - preserve YAML types correctly
            new_value_clean = new_value.strip()
            
            # Check if it's already properly quoted string
            if new_value_clean.startswith('"') and new_value_clean.endswith('"'):
                new_line = f"{key_part}: {new_value_clean}"
            # Check if it's an array
            elif new_value_clean.startswith('[') and new_value_clean.endswith(']'):
                new_line = f"{key_part}: {new_value_clean}"
            # Check if it's null
            elif new_value_clean.lower() == 'null':
                new_line = f"{key_part}: null"
            # Check if it's a boolean
            elif new_value_clean.lower() in ['true', 'false']:
                new_line = f"{key_part}: {new_value_clean.lower()}"
            # Check if it's a number (integer or float)
            elif new_value_clean.replace('.', '').replace('-', '').isdigit():
                new_line = f"{key_part}: {new_value_clean}"
            # Check if it's a memory specification (ends with 'g', 'm', etc.)
            elif new_value_clean[-1].lower() in 'gmk' and new_value_clean[:-1].replace('.', '').isdigit():
                new_line = f"{key_part}: \"{new_value_clean}\""
            else:
                # Default to quoted string for other values
                new_line = f"{key_part}: \"{new_value_clean}\""
        else:
            # For non-key-value lines, replace entirely but preserve indentation
            indent = len(original_line) - len(original_line.lstrip())
            if new_value.strip().startswith('"') and new_value.strip().endswith('"'):
                # Remove extra quotes if already quoted
                clean_value = new_value.strip()[1:-1]
                new_line = ' ' * indent + clean_value
            else:
                new_line = ' ' * indent + new_value.strip()
        
        # Update the line
        lines[line_number - 1] = new_line + '\n'
        
        # Write back to file
        with open(yaml_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        return f"Successfully modified line {line_number}: '{original_line}' -> '{new_line}'"
        
    except Exception as e:
        return f"Error modifying line {line_number}: {str(e)}"


@tool
def parse_edit_request(user_input: str) -> str:
    """
    Parse user input to extract line modification requests.
    
    Args:
        user_input: User's modification request
        
    Returns:
        Parsed edit commands as JSON string
    """
    import re
    import json
    
    try:
        edits = []
        
        # Pattern to match various edit request formats
        patterns = [
            r'line\s+(\d+).*?(?:to|with|as)\s+(.+?)(?:\s+and\s+line|\s*$)',
            r'change\s+line\s+(\d+).*?(?:to|with|as)\s+(.+?)(?:\s+and\s+line|\s*$)',
            r'modify\s+line\s+(\d+).*?(?:to|with|as)\s+(.+?)(?:\s+and\s+line|\s*$)',
            r'(\d+).*?(?:to|with|as)\s+(.+?)(?:\s+and\s+line|\s*$)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, user_input, re.IGNORECASE)
            for match in matches:
                line_num = int(match[0])
                value = match[1].strip()
                # Clean up the value
                value = value.rstrip(',').rstrip('and').strip()
                edits.append({"line_number": line_num, "new_value": value})
        
        if not edits:
            # Try simpler patterns
            line_match = re.search(r'line\s+(\d+)', user_input, re.IGNORECASE)
            if line_match:
                line_num = int(line_match.group(1))
                # Look for value after common keywords
                value_patterns = [r'(?:to|with|as)\s+(.+)', r':\s*(.+)', r'\s+(.+)']
                for vp in value_patterns:
                    value_match = re.search(vp, user_input[line_match.end():])
                    if value_match:
                        value = value_match.group(1).strip()
                        edits.append({"line_number": line_num, "new_value": value})
                        break
        
        return json.dumps(edits) if edits else json.dumps([])
        
    except Exception as e:
        return json.dumps([])


@tool
def validate_yaml_syntax(yaml_path: str) -> str:
    """
    Validate YAML file syntax.
    
    Args:
        yaml_path: Path to the YAML file
        
    Returns:
        Validation result message
    """
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        return "YAML syntax is valid"
        
    except yaml.YAMLError as e:
        return f"YAML syntax error: {str(e)}"
    except Exception as e:
        return f"Error validating YAML: {str(e)}"


def get_working_yaml_path(original_path: str) -> str:
    """
    Get the working YAML file path from original path.
    
    Args:
        original_path: Path to the original _orig.yaml file
        
    Returns:
        Path to the working .yaml file
    """
    if original_path.endswith('_orig.yaml'):
        return original_path.replace('_orig.yaml', '.yaml')
    else:
        return original_path.replace('.yaml', '_working.yaml')


def read_yaml_content(yaml_path: str) -> List[str]:
    """
    Read YAML file content as list of lines.
    
    Args:
        yaml_path: Path to the YAML file
        
    Returns:
        List of lines from the file
    """
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except Exception:
        return []