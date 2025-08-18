"""
Prompts for Supervisor Agent.
"""

# Agent descriptions for handoff decision making
AVAILABLE_AGENT_PROMPTS = {
    "parameterhandler": """YAML parameter file modification specialist.
    - Parameter Handler Agent
    - yaml parameter file modification
    - Handles all configuration file changes
    - Requires user approval for modifications
    - Interprets file paths and parameter formats
    """,

    "fileconverter": """Professional genotype and HLA imputation file conversion specialist
    - File Converter Agent
    - Genotype conversion: Various formats (.gen/.sample, .bgen/.sample, .tped/.tfam, .ped/.map, .pgen/.pvar/.psam, .vcf, .vcf.gz, .bcf) to PLINK binary (.bed, .bim, .fam)
    - Beagle v3 to VCF v4.1 conversion using beagle2vcf.jar
    - VCF v4.1 to Beagle v3 conversion using vcf2beagle.jar
    - HLA imputation tool (AXIOM, HIBAG, HLAHD, OPTITYPE, XHLA) output files converting to .hped format
    - LLM-powered natural language processing for conversion requests
    - Interactive workflow with parameter configuration support
    """,

    "hlaimputation": """Advanced HLA imputation analysis specialist
    - HLA Imputation Agent
    - PERFORMS HLA imputation using multiple professional tools (CookHLA, HLA-HD, OptiType)
    - Automatic tool discovery and intelligent tool selection
    - Supports PLINK binary and FASTQ input formats
    - Interactive workflow with workchain-based parameter handling
    - Superior replacement for legacy hlaimputation agent
    - Handles file conversion coordination when needed
    """,

    "hlafinemapping": """Advanced HLA fine mapping analysis specialist with customizable workflows
    - HLA Fine Mapping Agent
    - PERFORMS advanced HLA fine mapping with 5 customizable nodes
    - Interactive workflow customization (select nodes: node1, node2, node3, node4, node5)
    - Node1: HLA binary marker panel creation (essential for first-time users)
    - Node2: Regression analysis with visualization (Manhattan plots, heatmaps)
    - Node3: Stepwise conditional regression analysis
    - Node4: Omnibus test with automatic genotype phasing
    - Node5: Meta-analysis across multiple datasets
    - Workchain-based parameter handling and supervisor integration
    - Superior replacement for legacy hlafinemapping agent
    - Continuous workflow execution with user-defined node sequences
    """,

    "genotypephasing": """Genotype phasing operations
    - Genotype Phasing Agent
    - Performs genotype phasing using HATK/BEAGLE
    - Required for certain fine mapping analyses
    - Handles phased data output
    - Supports VCF, PLINK, and BEAGLE input formats
    """,

    "hlateacher": """HLA knowledge and education specialist
    - HLATeacher Agent
    - Answers questions ABOUT HLA (what is HLA, HLA types, genetics, biology)
    - Provides educational information and explanations
    - Handles conversational queries about HLA genetics
    - Use this for learning and understanding HLA concepts
    """
}

SUPERVISOR_PROMPTS = {
    "welcome_message": """ 
Welcome to the HLAgent!

I am here to help you orchestrate and coordinate various bioinformatics agents.
I can connect you with specialized agents for different tasks:

📋 AVAILABLE AGENTS:
• HLATeacher - Asking questions about HLA research by using Web search, RAG, and MCP servers.
• Genotype Phasing - Do genotype phasing job using BEAGLE.
• Parameter Handler - Do YAML(which include bioinformatics tool parameters) configuration modification.
• File Converter - Do Format conversion between different genotype formats and HLA imputation tool output to ".hped" format conversion.
• HLA Imputation - Do HLA imputation job using multiple professional tools (CookHLA, HLA-HD, OptiType, ...).
• HLA Fine Mapping - Do HLA fine mapping job with customizable fine mapping workflows (5 customizable nodes).

How can I help you today? You can ask me to:
- Connect you with a specific agent
- Ask questions about HLA genetics
- Perform genotype phasing
- Modify configuration files
- Convert file formats
- Or just chat about what you need!

Type 'help' for more information or 'Done!' to exit.
    """,
    
    "help_message": """
🔧 SUPERVISOR AGENT HELP

AVAILABLE COMMANDS:
• 'help' - Show this help message
• 'agents' - List all available agents
• 'status' - Show current session status
• 'Done!' - Exit the supervisor

EXAMPLE REQUESTS:
• "I need help with HLA genetics" → HLATeacher
• "I want to perform genotype phasing" → Genotype Phasing
• "I need to modify a YAML file" → Parameter Handler
• "Convert my files to PLINK format" → File Converter
• "Run HLA imputation analysis" → HLA Imputation
• "I need fine mapping analysis" → HLA Fine Mapping
• "I want customizable fine mapping with specific nodes" → HLA Fine Mapping

Just tell me what you need in natural language, and I'll connect you with the right agent!
    """,
    
    "agents_list": """
📋 REGISTERED AGENTS:

{agents_info}

Which agent would you like to work with?
    """,
    
    "handoff_message": """
🔄 HANDING OFF TO: {agent_name}

Task: {task_description}

The {agent_name} will now take over. When they're done, you'll return to me.
    """,
    
    "handoff_complete": """
✅ HANDOFF COMPLETED

The {agent_name} has completed their task. You're now back with the supervisor.
What would you like to do next?
    """,
    
    "handoff_error": """
❌ HANDOFF FAILED

There was an error handing off to {agent_name}:
{error_message}

Please try again or choose a different agent.
    """,
    
    "unknown_agent": """
❓ UNKNOWN AGENT

I don't recognize the agent "{agent_name}".

Available agents are:
{available_agents}

Please choose from the available agents.
    """,
    
    "no_agents": """
⚠️ NO AGENTS AVAILABLE

No agents are currently registered with the supervisor.
Please check the system configuration.
    """,
    
    "session_status": """
📊 SESSION STATUS

Session ID: {session_id}
Current State: {current_state}
Active Agent: {active_agent}
Registered Agents: {agent_count}
Messages in History: {message_count}
Current Task: {current_task}
    """,
    
    "goodbye_message": """
👋 GOODBYE!

Thank you for using the Supervisor Agent.
Your session has been completed.
    """,
    
    "error_message": """
❌ ERROR

An error occurred: {error_message}

Please try again or contact support if the problem persists.
    """,
    
    "invalid_input": """
❓ I don't understand that request.

Please try:
• Describing what you need (e.g., "I need genotype phasing")
• Typing 'help' for available commands
• Typing 'agents' to see available agents
• Typing 'Done!' or 'exit!' to exit
    """,
    
    "system_prompt": """
You are a professional supervisor agent that coordinates multiple specialized bioinformatics agents.

Your role is to:
1. Understand user requests and determine the appropriate agent
2. Facilitate handoffs between agents
3. Provide clear communication about what's happening
4. Handle errors gracefully
5. Maintain conversation flow

Available agents and their capabilities:
{available_agents}

Guidelines:
- Be helpful and professional
- Ask clarifying questions if the user's request is ambiguous
- Explain what each agent does before handing off
- Keep track of ongoing tasks
- Provide clear feedback about handoff status

Always respond in a friendly, professional manner and help users accomplish their bioinformatics tasks efficiently.
    """,
    
    "agent_selection_prompt": """
CRITICAL AGENT SELECTION TASK:

User Request: "{user_request}"

AVAILABLE AGENTS:
{available_agents}

DECISION RULES (CHECK IN THIS ORDER):

1. QUESTIONS vs EXECUTION:
   - If user asks "question", "what is", "how does", "explain", "tell me about", "learn about" → ALWAYS choose "hlateacher"
   - If user wants to "do", "perform", "run", "execute", "start" → Choose specific execution agent

2. EXECUTION AGENTS (only if user wants to DO something):
   - "fine mapping", "finemapping", "association", "nodes", "workflow" → "hlafinemapping"
   - "imputation", "impute" (for execution) → "hlaimputation"
   - "convert", "conversion", "format" → "fileconverter"
   - "phasing", "genotype phasing" → "genotypephasing"
   - "parameter", "yaml", "config" → "parameterhandler"

EXAMPLES:
- "I have questions about HLA imputation" → hlateacher (learning)
- "I want to do HLA imputation" → hlaimputation (execution)
- "What is fine mapping?" → hlateacher (learning)
- "I need fine mapping analysis" → hlafinemapping (execution)

Based on the request "{user_request}", respond with ONLY the agent name:
hlaimputation, hlafinemapping, fileconverter, genotypephasing, parameterhandler, or hlateacher
    """
}