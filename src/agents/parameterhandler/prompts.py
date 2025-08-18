"""
Prompts for Parameter Handler Agent.
"""

WELCOME_MESSAGE = """
🔧 === Parameter Handler Agent ===

I'm a professional YAML parameter file modifier for bioinformatics workflows.

I can help you modify YAML configuration files interactively.
When you're ready to finish, just say "Done!" and I'll show you the final result.

How to use:
- Specify line numbers and new values (e.g., "change line 12 to new_value")
- Make multiple changes (e.g., "line 12 to value1 and line 15 to value2")  
- Ask me to show the current file content anytime
- Say "Done!" when you're finished

Let's get started! 🚀
"""

YAML_DISPLAY_HEADER = """
📄 Current YAML file content:
{separator}
{content}
{separator}
"""

MODIFICATION_SUCCESS = """✅ Successfully modified line {line_number}:
   Before: {old_value}
   After:  {new_value}

What else would you like to change? (or say "Done!" to finish)"""

MODIFICATION_ERROR = """❌ Error modifying line {line_number}: {error}

Please try again with a valid line number and value."""

CONFIRMATION_MESSAGE = """
📄 Final YAML file content:
{separator}
{content}
{separator}

✅ All modifications completed!

Are you sure you want to finish? (Yes/No)
- Type "Yes" to confirm and complete the task
- Type "No" to continue making more changes
"""

TASK_COMPLETION = """
🎉 Task completed successfully!

The YAML file has been modified according to your requests.
All changes have been saved.

Thank you for using the Parameter Handler Agent! 👋
"""

HELP_MESSAGE = """
📋 Available commands:

🔧 Modification commands:
  - "change line 12 to new_value"
  - "modify line 5 to some_value"  
  - "line 8 to another_value"
  - "line 12 to value1 and line 15 to value2" (multiple changes)

📄 Display commands:
  - "show file" or "show content" - Display current file
  - "help" - Show this help message

🏁 Completion:
  - "Done!" - Finish editing and review changes

💡 Tips:
  - Line numbers start from 1
  - You can make multiple changes in one command
  - Values will be properly formatted for YAML
  - The file is automatically saved after each change
"""

ERROR_MESSAGES = {
    "file_not_found": "❌ Error: YAML file not found: {file_path}",
    "invalid_line": "❌ Error: Invalid line number {line_number}. File has {total_lines} lines.",
    "parse_error": "❌ Error: Could not understand your request. Type 'help' for examples.",
    "copy_error": "❌ Error: Could not create working copy of the file: {error}",
    "general_error": "❌ An unexpected error occurred: {error}"
}

AGENT_PROMPTS = {
    "system": """You are a professional YAML parameter file modification agent.

Your role:
1. Help users modify YAML configuration files for bioinformatics tools
2. Parse user requests for line modifications
3. Apply changes accurately and safely
4. Provide clear feedback on all operations
5. Maintain file integrity and proper YAML formatting

Guidelines:
- Always show line numbers when displaying file content
- Confirm each modification with before/after values
- Handle multiple modifications in a single request
- Validate YAML syntax after changes
- Be helpful and clear in all communications

When users say "Done!", show the final file and ask for confirmation before completing.""",

    "parse_modification_request": """You are an expert YAML modification parser. Parse the user's request to extract ONLY the EXPLICITLY requested line modifications.

User request: "{user_input}"

CRITICAL RULES:
1. Extract ONLY the line numbers and values that are EXPLICITLY mentioned by the user
2. Do NOT infer or add any additional modifications
3. If the user asks to change line 50 ONLY, return ONLY line 50
4. Do NOT include other line numbers unless they are explicitly mentioned

Examples:
- Input: "I want change 50 line to true" 
  Output: [{{"line_number": 50, "new_value": "true"}}]
- Input: "you have to change line index 12 to data/reference_panels"
  Output: [{{"line_number": 12, "new_value": "data/reference_panels"}}]
- Input: "line 28 to 18 and line 50 to true"
  Output: [{{"line_number": 28, "new_value": "18"}}, {{"line_number": 50, "new_value": "true"}}]

RETURN ONLY a valid JSON array of objects in this EXACT format:
[{{"line_number": <number>, "new_value": "<value>"}}, ...]

IMPORTANT:
- Extract ONLY explicitly mentioned line numbers
- ALL values must be strings (even numbers): "18", "true", "false", "null"
- Preserve quotes and brackets in values exactly as specified
- Return ONLY the JSON array, no other text
- If no valid modifications found, return []
- Do NOT add modifications that weren't explicitly requested""",

    "format_value": """Format the value appropriately for YAML.

Value: "{value}"
Original line: "{original_line}"

Consider:
- String values should be quoted if they contain special characters
- Lists should be formatted as [item1, item2, ...]
- Preserve the original key and indentation
- Maintain YAML syntax compliance

Return the properly formatted line."""
}

# Console formatting
SEPARATOR_LINE = "=" * 60
YAML_SEPARATOR = "-" * 50