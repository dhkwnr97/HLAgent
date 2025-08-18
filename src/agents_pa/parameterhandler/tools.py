"""
Tools for Parameter Handler Agent using PydanticAI.
Provides YAML file manipulation and parsing capabilities.
"""

import os
import json
import yaml
import shutil
from typing import List, Dict, Any, Union
from pathlib import Path
from pydantic_ai import RunContext

from .dependencies import ParameterHandlerDependencies
from .models import YamlEditRequest, YamlModificationResult


def copy_yaml_file(original_path: str) -> str:
    """Copy original YAML file to working file."""
    try:
        original_file = Path(original_path)
        if not original_file.exists():
            return f"Error: Original file {original_path} does not exist"
        
        # Create working file path by removing _orig
        if original_file.name.endswith('_orig.yaml'):
            working_name = original_file.name.replace('_orig.yaml', '.yaml')
            working_path = original_file.parent / working_name
        else:
            return f"Error: File must end with '_orig.yaml'"
        
        # Copy file
        shutil.copy2(original_path, working_path)
        return f"Successfully copied {original_path} to {working_path}"
        
    except Exception as e:
        return f"Error copying file: {str(e)}"


def read_yaml_with_line_numbers(yaml_path: str) -> str:
    """Read YAML file and return content with line numbers."""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        numbered_lines = []
        for i, line in enumerate(lines, 1):
            numbered_lines.append(f"{i:3d}: {line.rstrip()}")
        
        return "\n".join(numbered_lines)
        
    except Exception as e:
        return f"Error reading file: {str(e)}"


def read_yaml_content(yaml_path: str) -> List[str]:
    """Read YAML file content as list of lines."""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            return file.readlines()
    except Exception as e:
        return []


def modify_yaml_line(yaml_path: str, line_number: int, new_value: str) -> str:
    """Modify a specific line in YAML file."""
    try:
        # Read current content
        with open(yaml_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        # Validate line number
        if line_number < 1 or line_number > len(lines):
            return f"Error: Line number {line_number} is out of range (1-{len(lines)})"
        
        # Get the original line to preserve indentation and structure
        original_line = lines[line_number - 1]
        
        # Find the colon to preserve parameter name
        if ':' in original_line:
            param_name_part = original_line.split(':', 1)[0]
            # Preserve indentation and parameter name
            new_line = f"{param_name_part}: {new_value}\n"
        else:
            # If no colon, replace entire line but preserve indentation
            leading_spaces = len(original_line) - len(original_line.lstrip())
            new_line = ' ' * leading_spaces + str(new_value) + '\n'
        
        # Update the line
        lines[line_number - 1] = new_line
        
        # Write back to file
        with open(yaml_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)
        
        return f"Successfully modified line {line_number}"
        
    except Exception as e:
        return f"Error modifying line {line_number}: {str(e)}"


def validate_yaml_syntax(yaml_path: str) -> str:
    """Validate YAML file syntax."""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            yaml.safe_load(file)
        return "YAML syntax is valid"
    except yaml.YAMLError as e:
        return f"YAML syntax error: {str(e)}"
    except Exception as e:
        return f"Error validating YAML: {str(e)}"


async def parse_modification_request_llm(user_input: str) -> List[YamlEditRequest]:
    """Parse user modification request using LLM for natural language understanding."""
    from src.agents_pa.shared.universal_providers import get_parameterhandler_model
    from pydantic_ai import Agent
    
    # Create a temporary agent for parsing
    parsing_agent = Agent(
        model=get_parameterhandler_model(),
        system_prompt="You are a YAML modification parser that converts natural language requests into structured JSON."
    )
    
    parsing_prompt = f"""Parse the user's natural language request into a JSON array of YAML line modifications.

User request: "{user_input}"

Your task is to understand the user's intent and extract ALL modification requests from their natural language input.

Examples of user requests and expected JSON output:
- "Change line 13 to 19" → [{{"line_number": 13, "new_value": 19}}]
- "I want line 5 to be false and line 10 to hello" → [{{"line_number": 5, "new_value": false}}, {{"line_number": 10, "new_value": "hello"}}]
- "Set line 3 to data/output/myfile and also line 7 to ['A', 'B']" → [{{"line_number": 3, "new_value": "data/output/myfile"}}, {{"line_number": 7, "new_value": ["A", "B"]}}]
- "Update line 15 to true" → [{{"line_number": 15, "new_value": true}}]
- "Line 20 should be 42.5" → [{{"line_number": 20, "new_value": 42.5}}]

IMPORTANT RULES:
1. Return ONLY a valid JSON array, no other text
2. Detect ALL modifications mentioned in the request
3. Parse values correctly:
   - Numbers: use int or float (e.g., 42, 3.14)
   - Booleans: use true/false (not "true"/"false")
   - Arrays: use JSON array format ["item1", "item2"]
   - Strings: use quoted strings for text/paths
4. Extract line numbers accurately from natural language
5. Handle multiple modifications in one request

Parse this request: "{user_input}"

Return JSON array:"""
    
    try:
        # Use the parsing agent to understand natural language
        result = await parsing_agent.run(parsing_prompt)
        response = result.output
        
        # Clean up response 
        edits_json = response.strip()
        if edits_json.startswith('```json'):
            edits_json = edits_json[7:]
        if edits_json.endswith('```'):
            edits_json = edits_json[:-3]
        edits_json = edits_json.strip()
        
        # Remove any text before the JSON array
        import re
        json_match = re.search(r'\[.*\]', edits_json, re.DOTALL)
        if json_match:
            edits_json = json_match.group(0)
        
        # Parse JSON
        edits_data = json.loads(edits_json)
        
        # Convert to YamlEditRequest objects
        edits = []
        for edit in edits_data:
            if "line_number" in edit and "new_value" in edit:
                edits.append(YamlEditRequest(
                    line_number=int(edit["line_number"]),
                    new_value=edit["new_value"]
                ))
        
        return edits
        
    except Exception as e:
        # Fallback to simple pattern matching if LLM fails
        return parse_modification_request_simple(user_input)


def parse_modification_request_simple(user_input: str) -> List[YamlEditRequest]:
    """Simple pattern-based parsing as fallback."""
    edits = []
    
    # Simple parsing for basic cases like "line 19 to 18"
    import re
    
    # Pattern to match "line X to Y" format - try patterns in order and stop at first match
    patterns = [
        r'(?:change|modify|set|update)\s+line\s+(\d+).*?(?:to|with|as)\s+(.+?)(?:\s+and\s+line|\s*$)',
        r'line\s+(\d+).*?(?:to|with|as)\s+(.+?)(?:\s+and\s+line|\s*$)',
        r'\b(\d+)\s+(?:to|with|as)\s+(.+?)(?:\s+and\s+line|\s*$)'
    ]
    
    # Try patterns in order and use first successful match to avoid duplicates
    for pattern in patterns:
        matches = re.findall(pattern, user_input, re.IGNORECASE)
        if matches:  # If this pattern found matches, use only these and stop
            for match in matches:
                line_num = int(match[0])
                value_str = match[1].strip()
                
                # Try to parse value as appropriate type
                try:
                    # Try JSON parsing for lists, bools, etc.
                    if value_str.lower() in ['true', 'false']:
                        new_value = value_str.lower() == 'true'
                    elif value_str.startswith('[') and value_str.endswith(']'):
                        new_value = json.loads(value_str)
                    elif value_str.isdigit():
                        new_value = int(value_str)
                    else:
                        try:
                            new_value = float(value_str)
                        except ValueError:
                            new_value = value_str
                    
                    edits.append(YamlEditRequest(line_number=line_num, new_value=new_value))
                except:
                    # Default to string if parsing fails
                    edits.append(YamlEditRequest(line_number=line_num, new_value=value_str))
            break  # Stop after first successful pattern match
    
    return edits


def parse_modification_request(user_input: str) -> List[YamlEditRequest]:
    """Parse user modification request - backward compatibility wrapper for simple parsing."""
    return parse_modification_request_simple(user_input)


def get_file_info(yaml_path: str) -> Dict[str, Any]:
    """Get information about YAML file."""
    try:
        file_path = Path(yaml_path)
        if not file_path.exists():
            return {"error": f"File {yaml_path} does not exist"}
        
        with open(yaml_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        return {
            "path": str(file_path),
            "line_count": len(lines),
            "size_bytes": file_path.stat().st_size,
            "last_modified": file_path.stat().st_mtime,
            "exists": True
        }
    except Exception as e:
        return {"error": f"Error getting file info: {str(e)}"}