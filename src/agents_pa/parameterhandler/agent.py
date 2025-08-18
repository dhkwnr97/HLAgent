"""
Parameter Handler Agent using PydanticAI.

A simple YAML parameter file modification agent for workchain_pa integration.
Directly modifies YAML files without interactive sessions.
"""

import json
import os
from typing import Dict, Any, List
from pathlib import Path
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv

# Fix for event loop issues with Gemini models
from src.utils.event_loop_fix import apply_event_loop_fix
apply_event_loop_fix()

from src.agents_pa.shared.universal_providers import get_parameterhandler_model
from .dependencies import ParameterHandlerDependencies
from .models import YamlEditRequest, YamlModificationResult, AgentResponse, SessionState
from .tools import (
    copy_yaml_file, read_yaml_with_line_numbers, read_yaml_content,
    modify_yaml_line, validate_yaml_syntax, parse_modification_request, get_file_info
)


load_dotenv()


# Fresh agent creation function to prevent event loop issues
def get_fresh_parameter_handler_agent():
    """Create a fresh parameter handler agent to prevent event loop binding issues."""
    return Agent(
        model=get_parameterhandler_model(),
        deps_type=ParameterHandlerDependencies,
        system_prompt="""You are a professional YAML parameter file modification assistant for bioinformatics workflows.

Your role:
1. Help users interactively modify YAML configuration files
2. Parse natural language modification requests into structured edits
3. Apply modifications safely while preserving file structure
4. Provide clear feedback about changes made

Key capabilities:
- Parse requests like "change line 19 to 18" or "set line 47 to ['A', 'B', 'C']"
- Handle various data types: strings, integers, floats, booleans, lists
- Validate YAML syntax after modifications
- Show before/after values for transparency

Communication style:
- Be concise and professional
- Clearly explain what changes were made
- Ask for clarification when requests are ambiguous
- Confirm completion when user says "Done!"

Remember: Always preserve the parameter names (left side of ':') and only modify values (right side)."""
    )

# Create global agent with fresh creation pattern
parameter_handler_agent = get_fresh_parameter_handler_agent()


@parameter_handler_agent.tool
async def initialize_session(
    ctx: RunContext[ParameterHandlerDependencies], 
    original_yaml_path: str
) -> str:
    """Initialize parameter handler session with YAML file."""
    try:
        # Set up file paths
        ctx.deps.original_yaml_path = original_yaml_path
        working_path = ctx.deps.get_working_yaml_path()
        
        # Copy original file to working file
        copy_result = copy_yaml_file(original_yaml_path)
        if "Error" in copy_result:
            return f"❌ Failed to initialize: {copy_result}"
        
        # Read and display file content
        content_display = read_yaml_with_line_numbers(original_yaml_path)
        
        session_type = "standalone" if ctx.deps.is_standalone() else f"supervisor (requested by {ctx.deps.requester_agent})"
        
        return f"""🔧 **Parameter Handler Initialized** ({session_type})

**Current parameters:**
```
{content_display}
```

✅ Ready for modifications! Tell me what you'd like to change.

**Examples**:
- "Change line 47 to ['A', 'B', 'C']" 
- "Line 58 to false"
- Type "Done!" when finished"""
        
    except Exception as e:
        return f"❌ Error initializing session: {str(e)}"


@parameter_handler_agent.tool
async def parse_user_request(
    ctx: RunContext[ParameterHandlerDependencies], 
    user_input: str
) -> List[Dict[str, Any]]:
    """Parse user modification request into structured edits using LLM."""
    
    parsing_prompt = f"""Parse this YAML modification request into a JSON list of edits.

User request: "{user_input}"

Return ONLY a JSON array of objects with this format:
[{{"line_number": <int>, "new_value": <value>}}]

Where <value> can be:
- String: "text" 
- Integer: 123
- Float: 12.34
- Boolean: true/false
- Array: ["A", "B", "C"]

Examples:
- "change line 19 to 18" → [{{"line_number": 19, "new_value": 18}}]
- "modify line 47 to ['A', 'B', 'C']" → [{{"line_number": 47, "new_value": ["A", "B", "C"]}}]
- "set line 58 to false" → [{{"line_number": 58, "new_value": false}}]

Parse the request: "{user_input}"
"""
    
    try:
        # Create fresh agent to prevent event loop issues
        fresh_agent = get_fresh_parameter_handler_agent()
        response = await fresh_agent.run(parsing_prompt)
        
        # Clean up response - get the actual output from AgentRunResult
        edits_json = response.output.strip()
        if edits_json.startswith('```json'):
            edits_json = edits_json[7:]
        if edits_json.endswith('```'):
            edits_json = edits_json[:-3]
        edits_json = edits_json.strip()
        
        # Parse JSON
        edits = json.loads(edits_json)
        
        # Validate and convert to proper format
        parsed_edits = []
        for edit in edits:
            if "line_number" in edit and "new_value" in edit:
                parsed_edits.append({
                    "line_number": int(edit["line_number"]),
                    "new_value": edit["new_value"]
                })
        
        return parsed_edits
        
    except Exception as e:
        # Fallback to simple parsing
        simple_edits = parse_modification_request(user_input)
        return [{"line_number": edit.line_number, "new_value": edit.new_value} for edit in simple_edits]


@parameter_handler_agent.tool
async def apply_modifications(
    ctx: RunContext[ParameterHandlerDependencies], 
    edits: List[Dict[str, Any]]
) -> str:
    """Apply YAML modifications and return results."""
    if not edits:
        return "❌ No valid modifications found in your request. Please try again."
    
    working_path = ctx.deps.get_working_yaml_path()
    if not working_path:
        return "❌ No working file available. Please initialize session first."
    
    # Read current content for validation
    current_content = read_yaml_content(working_path)
    if not current_content:
        return f"❌ Cannot read working file: {working_path}"
    
    results = []
    successful_edits = 0
    
    # Remove duplicates (keep last edit for each line)
    unique_edits = {}
    for edit in edits:
        line_number = edit["line_number"]
        unique_edits[line_number] = edit
    
    # Apply each edit
    for line_number, edit in unique_edits.items():
        new_value = str(edit["new_value"])
        
        # Validate line number
        if line_number < 1 or line_number > len(current_content):
            results.append(f"❌ Line {line_number} is out of range (1-{len(current_content)})")
            continue
        
        # Get original value for display
        original_line = current_content[line_number - 1].strip()
        
        # Apply modification
        mod_result = modify_yaml_line(working_path, line_number, new_value)
        
        if "Successfully" in mod_result:
            results.append(f"✅ Line {line_number}: `{original_line}` → `{new_value}`")
            successful_edits += 1
            # Update cached content
            current_content = read_yaml_content(working_path)
        else:
            results.append(f"❌ Line {line_number}: {mod_result}")
    
    # Validate YAML syntax
    validation = validate_yaml_syntax(working_path)
    if "error" in validation.lower():
        results.append(f"⚠️  **YAML Syntax Warning**: {validation}")
    
    # Format response
    response = f"**Modifications Applied** ({successful_edits}/{len(unique_edits)} successful):\n\n"
    response += "\n".join(results)
    
    if successful_edits > 0:
        response += f"\n\n💾 Changes saved to: `{working_path}`"
        response += "\n\nWhat else would you like to change? (or type 'Done!' to finish)"
    
    return response


@parameter_handler_agent.tool
async def show_current_file(ctx: RunContext[ParameterHandlerDependencies]) -> str:
    """Display current YAML file content with line numbers."""
    working_path = ctx.deps.get_working_yaml_path()
    if not working_path:
        return "❌ No working file available."
    
    content_display = read_yaml_with_line_numbers(working_path)
    
    return f"""📄 **Current YAML File**: `{working_path}`

```
{content_display}
```

What would you like to change?"""


@parameter_handler_agent.tool
async def finalize_session(ctx: RunContext[ParameterHandlerDependencies]) -> str:
    """Show final file content and ask for confirmation."""
    working_path = ctx.deps.get_working_yaml_path()
    if not working_path:
        return "❌ No working file available."
    
    content_display = read_yaml_with_line_numbers(working_path)
    
    return f"""📋 **Final YAML Configuration**:

```
{content_display}
```

🤔 **Are you sure you want to finish modifying parameters?**

Reply with:
- **"Yes"** to complete the session
- **"No"** to continue making changes"""


async def handle_workchain_request(
    original_yaml_path: str, 
    requester_agent: str = "workchain_pa", 
    task_id: str = ""
) -> Dict[str, Any]:
    """Handle YAML modification request directly from workchain_pa."""
    
    # Create dependencies
    deps = ParameterHandlerDependencies.create_default(
        session_id=f"param_{hash(original_yaml_path)}",
        requester_agent=requester_agent,
        task_id=task_id,
        original_yaml_path=original_yaml_path
    )
    
    try:
        # Initialize session and display current content directly
        deps.original_yaml_path = original_yaml_path
        working_path = deps.get_working_yaml_path()
        
        # Copy original file to working file
        copy_result = copy_yaml_file(original_yaml_path)
        if "Error" in copy_result:
            print(f"❌ Failed to initialize: {copy_result}")
            return {"status": "error", "message": copy_result}
        
        # Read and display file content
        content_display = read_yaml_with_line_numbers(original_yaml_path)
        session_type = "workchain_pa" if deps.requester_agent == "workchain_pa" else f"supervisor (requested by {deps.requester_agent})"
        
        init_response = f"""🔧 **Parameter Handler Initialized** ({session_type})

**Current parameters:**
```
{content_display}
```

============================================================
If you want to use Streamlit Web UI for parameter modification, copy&paste this yaml path:
\n{deps.original_yaml_path}\n
After using web ui, you can directly chat "Done!" -> "Yes" to finish
============================================================

✅ Ready for modifications! Tell me what you'd like to change.

**Examples**:
- "Change line 19 to 18"
- "Set line 47 to ['A', 'B', 'C']" 
- "Line 58 to false"
**Type "Done!" when parameter modification finished**"""
        print(init_response)
        
        # Interactive loop for modifications
        while True:
            try:
                user_input = input("\n➤ ").strip()
                
                if user_input.lower() in ["exit", "quit", "abort"]:
                    print("❌ Session aborted.")
                    return {"status": "aborted", "working_file": deps.get_working_yaml_path()}
                
                # Handle completion request
                if user_input.lower() == "done!":
                    # Show final content and ask for confirmation
                    working_path = deps.get_working_yaml_path()
                    if not working_path:
                        print("❌ No working file available.")
                        continue
                    
                    content_display = read_yaml_with_line_numbers(working_path)
                    
                    finalize_response = f"""📋 **Final YAML Configuration**:

```
{content_display}
```

🤔 **Are you sure you want to finish modifying parameters?**

Reply with:
- **"Yes"** to complete the session
- **"No"** to continue making changes"""
                    print(finalize_response)
                    
                    # Wait for user confirmation
                    while True:
                        confirm_input = input("\n➤ ").strip().lower()
                        if confirm_input == "yes":
                            print("✅ **Parameter modification completed successfully!**")
                            return {
                                "status": "completed",
                                "working_file": deps.get_working_yaml_path(),
                                "original_file": deps.original_yaml_path,
                                "requester": deps.requester_agent,
                                "task_id": deps.task_id
                            }
                        elif confirm_input == "no":
                            print("↩️  **Continuing with modifications...**")
                            break
                        else:
                            print("Please reply with 'Yes' to finish or 'No' to continue making changes.")
                    continue
                
                # Handle help requests
                if user_input.lower() in ["help", "?", "commands"]:
                    print("""
🔧 **Parameter Handler Commands**:

**Modification Examples**:
- "Change line 19 to 18"
- "Set line 47 to ['A', 'B', 'C']"
- "Line 58 to false"
- "Update line 23 to 'new_value'"

**Other Commands**:
- "show file" - Display current file content
- "Done!" - Finish modifications
- "help" - Show this help
- "exit" - Abort session""")
                    continue
                
                # Handle file display
                if user_input.lower() in ["show file", "show", "display", "view"]:
                    working_path = deps.get_working_yaml_path()
                    if not working_path:
                        print("❌ No working file available.")
                        continue
                    
                    content_display = read_yaml_with_line_numbers(working_path)
                    file_response = f"""📄 **Current YAML File**: `{working_path}`

```
{content_display}
```

What would you like to change?"""
                    print(file_response)
                    continue
                
                # Parse and apply modifications
                if user_input:
                    # Parse request using LLM with comprehensive natural language understanding
                    parsing_prompt = f"""You are a YAML modification parser. Parse the user's natural language request into a JSON array of YAML line modifications.

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
                        # Create fresh agent to prevent event loop issues
                        fresh_agent = get_fresh_parameter_handler_agent()
                        response = await fresh_agent.run(parsing_prompt)
                        
                        # Clean up response - get the actual output from AgentRunResult
                        edits_json = response.output.strip()
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
                        import json
                        edits = json.loads(edits_json)
                        
                        # Validate and convert to proper format
                        parsed_edits = []
                        for edit in edits:
                            if "line_number" in edit and "new_value" in edit:
                                parsed_edits.append({
                                    "line_number": int(edit["line_number"]),
                                    "new_value": edit["new_value"]
                                })
                        
                        edits = parsed_edits
                        
                        if not edits:
                            print("❌ No valid modifications found in your request. Please specify line numbers and new values.")
                            continue
                            
                    except Exception as e:
                        print(f"❌ Could not understand your request: {str(e)}")
                        print("Please try using clear format like: 'Change line 5 to new_value' or 'Line 3 to hello and line 7 to 42'")
                        continue
                    
                    if edits:
                        # Apply modifications directly
                        working_path = deps.get_working_yaml_path()
                        if not working_path:
                            print("❌ No working file available.")
                            continue
                        
                        # Read current content for validation
                        current_content = read_yaml_content(working_path)
                        if not current_content:
                            print(f"❌ Cannot read working file: {working_path}")
                            continue
                        
                        results = []
                        successful_edits = 0
                        
                        # Apply each edit
                        for edit in edits:
                            line_number = edit["line_number"]
                            new_value = str(edit["new_value"])
                            
                            # Validate line number
                            if line_number < 1 or line_number > len(current_content):
                                results.append(f"❌ Line {line_number} is out of range (1-{len(current_content)})")
                                continue
                            
                            # Get original value for display
                            original_line = current_content[line_number - 1].strip()
                            
                            # Apply modification
                            mod_result = modify_yaml_line(working_path, line_number, new_value)
                            
                            if "Successfully" in mod_result:
                                results.append(f"✅ Line {line_number}: `{original_line}` → `{new_value}`")
                                successful_edits += 1
                                # Update cached content
                                current_content = read_yaml_content(working_path)
                            else:
                                results.append(f"❌ Line {line_number}: {mod_result}")
                        
                        # Validate YAML syntax
                        validation = validate_yaml_syntax(working_path)
                        if "error" in validation.lower():
                            results.append(f"⚠️  **YAML Syntax Warning**: {validation}")
                        
                        # Format response
                        response = f"**Modifications Applied** ({successful_edits}/{len(edits)} successful):\n\n"
                        response += "\n".join(results)
                        
                        if successful_edits > 0:
                            response += "\n\nWhat else would you like to change? (or type 'Done!' to finish)"
                        
                        print(response)
                    else:
                        print("❌ Could not understand your request. Try: 'change line X to Y'")
                
            except KeyboardInterrupt:
                print("\n❌ Session interrupted.")
                return {"status": "interrupted", "working_file": deps.get_working_yaml_path()}
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                continue
    
    except Exception as e:
        print(f"❌ Session error: {str(e)}")
        return {"status": "error", "message": str(e)}


# For supervisor integration (legacy)
async def handle_supervisor_request(
    original_yaml_path: str, 
    requester_agent: str, 
    task_id: str
) -> Dict[str, Any]:
    """Handle parameter modification request from supervisor (legacy function)."""
    return await handle_workchain_request(
        original_yaml_path=original_yaml_path,
        requester_agent=requester_agent,
        task_id=task_id
    )