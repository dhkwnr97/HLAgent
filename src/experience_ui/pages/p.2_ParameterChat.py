"""
Parameter Handler Interactive Chat Interface for Streamlit.
Provides web UI for interactive parameter modification instead of console input.
"""

import streamlit as st
import asyncio
import sys
import os
import json
from typing import Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add the project root to Python path
project_root = os.getenv("HLAGENT_MAIN_DIRECTORY")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.agents_pa.parameterhandler.agent import (
    get_fresh_parameter_handler_agent, 
    parameter_handler_agent
)
from src.agents_pa.parameterhandler.dependencies import ParameterHandlerDependencies
from src.agents_pa.parameterhandler.tools import (
    copy_yaml_file, read_yaml_with_line_numbers, read_yaml_content,
    modify_yaml_line, validate_yaml_syntax
)

# Configure Streamlit page
st.set_page_config(
    page_title="Parameter Handler Chat",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def initialize_parameter_session_state():
    """Initialize session state variables for parameter handler."""
    if "param_messages" not in st.session_state:
        st.session_state.param_messages = []
    
    if "param_deps" not in st.session_state:
        st.session_state.param_deps = None
    
    if "param_session_active" not in st.session_state:
        st.session_state.param_session_active = False
    
    if "param_yaml_path" not in st.session_state:
        st.session_state.param_yaml_path = ""
    
    if "param_waiting_for_confirmation" not in st.session_state:
        st.session_state.param_waiting_for_confirmation = False

def display_parameter_chat_history():
    """Display parameter handler chat messages."""
    for message in st.session_state.param_messages:
        role = message["role"]
        content = message["content"]
        
        avatar = "👤" if role == "user" else "⚙️"
        
        with st.chat_message(role, avatar=avatar):
            if role == "assistant":
                st.caption("Agent: Parameter Handler")
            st.markdown(content)

async def initialize_parameter_session(yaml_path: str) -> str:
    """Initialize parameter handler session with YAML file."""
    try:
        # Create dependencies
        st.session_state.param_deps = ParameterHandlerDependencies.create_default(
            session_id=f"param_ui_{hash(yaml_path)}",
            requester_agent="streamlit_ui",
            original_yaml_path=yaml_path
        )
        
        # Set up file paths
        st.session_state.param_deps.original_yaml_path = yaml_path
        working_path = st.session_state.param_deps.get_working_yaml_path()
        
        # Copy original file to working file
        copy_result = copy_yaml_file(yaml_path)
        if "Error" in copy_result:
            return f"L Failed to initialize: {copy_result}"
        
        # Read and display file content
        content_display = read_yaml_with_line_numbers(yaml_path)
        
        return f"""⚙️ **Parameter Handler Initialized** (Streamlit UI)

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
        return f"L Error initializing session: {str(e)}"

async def parse_user_modification_request(user_input: str) -> List[Dict[str, Any]]:
    """Parse user modification request using LLM."""
    parsing_prompt = f"""You are a YAML modification parser. Parse the user's natural language request into a JSON array of YAML line modifications.

User request: "{user_input}"

Your task is to understand the user's intent and extract ALL modification requests from their natural language input.

Examples of user requests and expected JSON output:
- "Change line 13 to 19" ⚙️ [{{"line_number": 13, "new_value": 19}}]
- "I want line 5 to be false and line 10 to hello" ⚙️ [{{"line_number": 5, "new_value": false}}, {{"line_number": 10, "new_value": "hello"}}]
- "Set line 3 to data/output/myfile and also line 7 to ['A', 'B']" ⚙️ [{{"line_number": 3, "new_value": "data/output/myfile"}}, {{"line_number": 7, "new_value": ["A", "B"]}}]
- "Update line 15 to true" ⚙️ [{{"line_number": 15, "new_value": true}}]
- "Line 20 should be 42.5" ⚙️ [{{"line_number": 20, "new_value": 42.5}}]

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
        st.error(f"Could not parse your request: {str(e)}")
        return []

async def apply_parameter_modifications(edits: List[Dict[str, Any]]) -> str:
    """Apply YAML modifications and return results."""
    if not edits:
        return "L No valid modifications found in your request. Please try again."
    
    if not st.session_state.param_deps:
        return "L No session active. Please initialize first."
    
    working_path = st.session_state.param_deps.get_working_yaml_path()
    if not working_path:
        return "L No working file available. Please initialize session first."
    
    # Read current content for validation
    current_content = read_yaml_content(working_path)
    if not current_content:
        return f"L Cannot read working file: {working_path}"
    
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
            results.append(f"L Line {line_number} is out of range (1-{len(current_content)})")
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
            results.append(f"L Line {line_number}: {mod_result}")
    
    # Validate YAML syntax
    validation = validate_yaml_syntax(working_path)
    if "error" in validation.lower():
        results.append(f"⚠️  **YAML Syntax Warning**: {validation}")
    
    # Format response
    response = f"**Modifications Applied** ({successful_edits}/{len(unique_edits)} successful):\n\n"
    response += "\n".join(results)
    
    if successful_edits > 0:
        response += f"\n\n✅ Changes saved to: `{working_path}`"
        response += "\n\nWhat else would you like to change? (or type 'Done!' to finish)"
    
    return response

def show_current_yaml_file() -> str:
    """Display current YAML file content with line numbers."""
    if not st.session_state.param_deps:
        return "L No session active."
    
    working_path = st.session_state.param_deps.get_working_yaml_path()
    if not working_path:
        return "L No working file available."
    
    content_display = read_yaml_with_line_numbers(working_path)
    
    return f"""⚙️ **Current YAML File**: `{working_path}`

```
{content_display}
```

What would you like to change?"""

def show_final_confirmation() -> str:
    """Show final file content and ask for confirmation."""
    if not st.session_state.param_deps:
        return "L No session active."
    
    working_path = st.session_state.param_deps.get_working_yaml_path()
    if not working_path:
        return "L No working file available."
    
    content_display = read_yaml_with_line_numbers(working_path)
    
    return f"""⚙️ **Final YAML Configuration**:

```
{content_display}
```

🤔 **Are you sure you want to finish modifying parameters?**

Reply with:
- **"Yes"** to complete the session
- **"No"** to continue making changes"""

def create_parameter_sidebar():
    """Create sidebar for parameter handler."""
    with st.sidebar:
        st.header("⚙️ Parameter Handler")
        
        # Session status
        if st.session_state.param_session_active:
            st.success("🔄 **Session Active**")
            if st.session_state.param_deps:
                working_file = st.session_state.param_deps.get_working_yaml_path()
                st.info(f"⏳ Working on: `{os.path.basename(working_file) if working_file else 'N/A'}`")
        else:
            st.warning("❌ **No Session**")
        
        st.divider()
        
        # File initialization
        st.subheader("⚙️ Initialize Session")
        
        # File path input
        yaml_path = st.text_input(
            "YAML File Path", 
            value=st.session_state.param_yaml_path,
            placeholder="e.g., data/configs/example_orig.yaml",
            help="Path to the original YAML configuration file"
        )
        
        if st.button("🔧 Start Parameter Session", type="primary"):
            if yaml_path and os.path.exists(yaml_path):
                st.session_state.param_yaml_path = yaml_path
                st.session_state.param_session_active = True
                st.session_state.param_messages = []
                st.session_state.param_waiting_for_confirmation = False
                
                # Initialize session
                init_response = asyncio.run(initialize_parameter_session(yaml_path))
                
                # Add initialization message
                st.session_state.param_messages.append({
                    "role": "assistant",
                    "content": init_response
                })
                
                st.rerun()
            else:
                st.error("L Please provide a valid YAML file path")
        
        st.divider()
        
        # Session controls
        if st.session_state.param_session_active:
            if st.button("⚙️ Show Current File"):
                file_content = show_current_yaml_file()
                st.session_state.param_messages.append({
                    "role": "assistant",
                    "content": file_content
                })
                st.rerun()
            
            if st.button("🗑️ Clear Chat", type="secondary"):
                st.session_state.param_messages = []
                st.rerun()
            
            if st.button("🚪 End Session", type="secondary"):
                st.session_state.param_session_active = False
                st.session_state.param_deps = None
                st.session_state.param_messages = []
                st.session_state.param_waiting_for_confirmation = False
                st.rerun()
        
        st.divider()
        
        # Help section
        st.subheader("⚙️ Commands")
        with st.expander("Modification Examples"):
            st.markdown("""
            - "Change line 19 to 18"
            - "Set line 47 to ['A', 'B', 'C']"
            - "Line 58 to false"
            - "Update line 23 to 'new_value'"
            """)
        
        with st.expander("Other Commands"):
            st.markdown("""
            - "show file" - Display current content
            - "Done!" - Finish modifications
            - "help" - Show help
            """)

def main():
    """Main Streamlit application for parameter handler chat."""
    st.title("⚙️ Parameter Handler Interactive Chat")
    st.markdown("**Interactive YAML parameter modification - Web UI instead of console**")
    
    # Initialize session state
    initialize_parameter_session_state()
    
    # Create sidebar
    create_parameter_sidebar()
    
    # Main chat interface
    if not st.session_state.param_session_active:
        st.info("**Please initialize a session using the sidebar to get started**")
        st.markdown("""
        ### How to use:
        1. **Enter YAML file path** in the sidebar (e.g., `data/configs/example_orig.yaml`)
        2. **Click "Start Parameter Session"** to initialize
        3. **Chat with the Parameter Handler** to modify YAML parameters
        4. **Type "Done!"** when finished, then confirm with "Yes"
        
        ### Example workflow:
        - User: "Change line 19 to 18"
        - Agent: Shows the modification and asks for more changes
        - User: "Done!"
        - Agent: Shows final YAML and asks "Are you sure?"
        - User: "Yes" (completes the session)
        """)
        return
    
    # Display chat history
    display_parameter_chat_history()
    
    # Chat input
    if st.session_state.param_session_active:
        if prompt := st.chat_input("Tell me what parameter changes you'd like to make..."):
            # Add user message to chat history
            st.session_state.param_messages.append({
                "role": "user", 
                "content": prompt
            })
            
            # Display user message
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)
            
            # Process message
            with st.chat_message("assistant", avatar="⚙️"):
                response_placeholder = st.empty()
                
                # Handle different types of requests
                user_input_lower = prompt.strip().lower()
                
                if user_input_lower == "done!":
                    # Show final confirmation
                    st.session_state.param_waiting_for_confirmation = True
                    response = show_final_confirmation()
                
                elif st.session_state.param_waiting_for_confirmation:
                    if user_input_lower == "yes":
                        response = "✅ **Parameter modification completed successfully!**"
                        st.session_state.param_session_active = False
                        st.session_state.param_waiting_for_confirmation = False
                        st.balloons()
                    elif user_input_lower == "no":
                        response = "↩️ **Continuing with modifications...** What would you like to change?"
                        st.session_state.param_waiting_for_confirmation = False
                    else:
                        response = "Please reply with 'Yes' to finish or 'No' to continue making changes."
                
                elif user_input_lower in ["show file", "show", "display", "view"]:
                    response = show_current_yaml_file()
                
                elif user_input_lower in ["help", "?", "commands"]:
                    response = """
=' **Parameter Handler Commands**:

**Modification Examples**:
- "Change line 19 to 18"
- "Set line 47 to ['A', 'B', 'C']"
- "Line 58 to false"
- "Update line 23 to 'new_value'"

**Other Commands**:
- "show file" - Display current file content
- "Done!" - Finish modifications
- "help" - Show this help"""
                
                else:
                    # Parse and apply modifications
                    with st.spinner("Processing your request..."):
                        edits = asyncio.run(parse_user_modification_request(prompt))
                        if edits:
                            response = asyncio.run(apply_parameter_modifications(edits))
                        else:
                            response = "L Could not understand your request. Try: 'change line X to Y'"
                
                # Display response
                response_placeholder.markdown(response)
                st.caption("Agent: Parameter Handler")
            
            # Add assistant response to chat history
            st.session_state.param_messages.append({
                "role": "assistant", 
                "content": response
            })
            
            # Rerun to update the interface
            st.rerun()

if __name__ == "__main__":
    main()