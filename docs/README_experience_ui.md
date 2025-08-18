# HLAgent Streamlit Multi-Page Web UI

A Streamlit-based web interface for the HLAgent multi-agent system.

## Overview

This multi-page web application provides a web-based interface for HLAgent, minimizing console-based interactions to a modern web UI experience.

## Pages

### 🤖 p.1_Chatting - Multi-Agent Chat Interface
Interactive chat with HLAgent(Supervisor and specialist agents) including automatic delegation.

**Features:**
- Chat with HLAgent(Supervisor and specialist agents) that automatically delegates to specialists
- Direct interaction with HLA Teacher, File Converter, Parameter Handler, etc.
- Real-time streaming responses for HLA Teacher
- Session management and handover tracking
- Visual agent status indicators

### ⚙️ p.2_ParameterChat - Interactive Parameter Modification
Web-based YAML parameter editing instead of console input.

**Features:**
- Interactive YAML parameter modification through natural language
- Web UI replacement for console-based parameter handling
- After workflow finished enter in console: "Done!" → "Are you sure?" → "Yes"
- Real-time file content display

### 📊 p.3_ReportViewer - Beautiful Report Viewer
Viewer for HTML reports, plots, and analysis results.

**Features:**
- Beautiful display of HTML reports and interactive plots
- Image and PDF file viewer with embedded display
- Advanced filtering system with multiple criteria
- Recursive folder scanning of analysis results
- Smart file organization by analysis type

## Installation

1. Install required dependencies:
```bash
./setup.sh
```
2. Set up environment variables in `.env` file
3. Ensure HLAGENT_MAIN_DIRECTORY is properly configured

## Usage

Run the Streamlit multi-page app:
```bash
streamlit run src/experience_ui/app.py
```

The web interface will open at `http://localhost:8501` with page navigation in the sidebar.

## Quick Start Guides

### Multi-Agent Chatting
1. Navigate to **p.1_Chatting** page
2. Chat with HLAgent(Supervisor and specialist agents) - it automatically routes queries to appropriate specialists
3. Ask HLA questions → Delegates to HLA Teacher
4. Ask file conversion → Delegates to File Converter
5. Type "Done!" to return control to HLAgent(supervisor agent)

### Parameter Modification
1. Navigate to **p.2_ParameterChat** page
2. Enter YAML file path (e.g., `data/configs/example_orig.yaml`)
3. Click "Start Parameter Session"
4. Use natural language: "Change line 19 to 18", "Set line 47 to ['A', 'B', 'C']"
5. Type "Done!" when finished, confirm with "Yes"

### Report Viewing
1. Navigate to **p.3_ReportViewer** page
2. Configure filters:
   - **Prefixes**: File name prefixes (e.g., "heatmap", "manhattan")
   - **Extensions**: File types (e.g., .html, .png, .pdf)
   - **Filter Words**: Words that must be in filename (AND condition)
3. Click "Scan data/output Folder"
4. Select files from dropdown to view beautifully rendered content

## Filter Logic (Report Viewer)

The report viewer uses advanced filtering logic:
- **(Prefixes OR Extensions) AND Filter Words**
- Example: filter words "RA" → finds files containing "RA" AND matching prefixes/extensions
- Supports multiple filter words with ALL must match (AND condition)

## Supported File Types

### Report Viewer
- **📊 Interactive HTML plots** (Plotly, matplotlib with embedded display)
- **🖼️ Image files** (PNG, JPG, JPEG with full-size display)
- **📄 PDF reports** (embedded PDF viewer)

### Parameter Handler
- **📝 YAML configuration files** with line-by-line editing

## Architecture

### Multi-Page Structure
- `app.py` - Main landing page with navigation and project overview
- `pages/p.1_Chatting.py` - Multi-agent chat interface
- `pages/p.2_ParameterChat.py` - Parameter handler web UI
- `pages/p.3_ReportViewer.py` - Report and file viewer

### Integration
- Uses PydanticAI-based agent system
- Maintains session state across page navigation
- Handles async agent operations
- Dual-mode support (console + web UI) for parameter handling

## Key Benefits

1. **Minimal Console Interactions** - Almost all moved to web UI
2. **Natural Language Processing** - Intuitive parameter modifications
3. **Beautiful Visualizations** - Proper rendering of analysis results
4. **Smart File Management** - Advanced filtering and organization
5. **Session Persistence** - Maintains state across interactions
6. **Multi-Agent Coordination** - Seamless specialist delegation

## Development Notes

- Built with Streamlit multi-page architecture
- Async/await patterns for agent interactions
- Session state management for complex workflows
- Event loop handling for different execution contexts
- Environment variable configuration with python-dotenv