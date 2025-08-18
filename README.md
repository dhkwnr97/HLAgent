# HLAgent

A multi-agent system for comprehensive HLA (Human Leukocyte Antigen) genomic analysis. HLAgent
provides specialized capabilities including HLA imputation, fine mapping, genotype phasing, file conversion, and
question answering support through AI-powered agents.

## 🏗️ Architecture

HLAgent implements a multi-agent architecture with intelligent handoff capabilities:

```
┌─────────────────────────────────────────────────────────────────────┐
│                          HLAgent System                             │
├─────────────────────────────────────────────────────────────────────┤
│                         Supervisor Agent                            │
│                  (Orchestrates & Manages Handoffs)                  │
├─────────────────────────────────────────────────────────────────────┤
│                      Specialized Sub-Agents                         │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┤
│ HLA         │ HLA         │ Genotype    │ File        │ Parameter   │
│ Imputation  │ Fine        │ Phasing     │ Converter   │ Handler     │
│ Agent       │ Mapping     │ Agent       │ Agent       │ Agent       │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│             │ HLA         │             │             │             │
│             │ Teacher     │             │             │             │
│             │ Agent       │             │             │             │
├─────────────────────────────────────────────────────────────────────┤
│                     Integration Layer                               │
├─────────────┬─────────────┬─────────────┬───────────────────────────┤
│ Google A2A  │ MCP Server  │ RAG System  │      Interfaces           │
│ Protocol    │ Support     │ ChromaDB    │ GUI (Streamlit) | CLI     │
└─────────────┴─────────────┴─────────────┴───────────────────────────┘
```

### Agent Implementations

- **`src/agents_pa`**: GUI agents built with PydanticAI for structured data handling
- **`src/agents`**: CLI agents built with LangChain and LangGraph

## 🚀 Features

- **Multi-Agent System**: Supervisor agent orchestrates specialized sub-agents
- **HLA Analysis Suite**: Comprehensive genomic analysis capabilities
    - **HLA Imputation
    - **HLA Fine Mapping
    - **Genotype/Haplotype Phasing
    - **Genotype File Conversion
    - **HLA Q&A
    - **Parameter Management
- **Multiple Interfaces**:
    - GUI (Streamlit web interface)
    - CLI (Command-line interface)
    - A2A Protocol support
- **Knowledge Integration**:
    - RAG system with ChromaDB
    - MCP (Model Context Protocol) server support
    - Web-based search capabilities
- **LLM Support**:
    - Local LLMs via Ollama
    - External providers (OpenAI, Anthropic, Google gen AI)
    - Multiple provider backends (Hugging Face, Groq, Google Vertex AI)

## 📋 Prerequisites

Before installing HLAgent, ensure you have:
- **Anaconda or Miniconda**
- **Git**

## ⚙️ Installation

### Quick Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd HLAgent-main
```

2. Run the automated setup script:
```bash
./setup.sh
```

The setup script will:
- Create a conda environment named `hlagent`
- Install all Python dependencies
- Set up directory structure
- Install Ollama and default model (`llama3.1:8b`)
- Configure environment variables

### Manual Setup

If you prefer manual installation:

1. Create conda environment:
```bash
conda env create -f environment.yml
conda activate hlagent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Ollama (for local LLM):
```bash
# Visit https://ollama.com/search for model selection
ollama pull llama3.1:8b
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file with the following parameters:

```bash
# Required
HLAGENT_MAIN_DIRECTORY=/path/to/your/HLAgent-main
DEFAULT_LLM_PROVIDER=ollama  # or openai, anthropic, gemini
DEFAULT_LLM_MODEL=llama3.1:8b # or gpt-5-nano, claude-sonnet-4-0, gemini-2.5-flash 

# API Keys (optional, depending on provider choice)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_API_KEY=your_google_api_key_here

# For HLA Teacher Agent web search
TAVILY_API_KEY=your_tavily_api_key_here

# Ollama settings (if using local LLM)
OLLAMA_BASE_URL=http://localhost:11434
```

### Knowledge Base Setup

For the RAG system:
1. Place PDF, TXT, or MD documents in `data/knowledge/Articles/`
2. The agent will automatically index them into ChromaDB on startup

#### 2 Example articles

1. Medhasi, Sadeep, and Narisara Chantratita. “Human Leukocyte Antigen (HLA) System: Genetics and Association with Bacterial and Viral Infections.” Journal of Immunology Research, edited by Cinzia Ciccacci, Wiley, May 2022, pp. 1–15. Crossref, doi:10.1155/2022/9710376.
2. Naito, Tatsuhiko, and Yukinori Okada. “HLA Imputation and Its Application to Genetic and Molecular Fine-Mapping of the MHC Region in Autoimmune Diseases.” Seminars in Immunopathology, no. 1, Springer Science and Business Media LLC, Nov. 2021, pp. 15–28. Crossref, doi:10.1007/s00281-021-00901-9.

### MCP Server Configuration

Configure MCP servers in `config/mcp_config_HLAgent.json`:
```json
{
    "mcpServers": {
        "fetch": {
            "command": "uvx",
            "args": ["mcp-server-fetch"]
        },
        "brave-search": {
            "command": "docker",
            "args": ["run", "-i", "--rm", "-e", "BRAVE_API_KEY", "mcp/brave-search"],
          "env": {
             "BRAVE_API_KEY": "enter_your_brave_api_key"
          }
        }
    }
}
```

## 🖥️ Usage

### GUI Interface (Streamlit)

Start the web interface:
```bash
./run.sh
```

Access the application at `http://localhost:8501`

### CLI Interface

Run the supervisor agent directly:
```bash
python -m src.agents.supervisor
```

### Agent Interaction Modes

Within the HLA Teacher Agent, use these commands:
- `/web` - Web-based search mode
- `/rag` - RAG system with web search
- `/mcp` - MCP server integration mode

### A2A Protocol Support

Start the A2A server:
```bash
python src/a2a/server.py
```

In another terminal, start the client:
```bash
python src/a2a/client.py
```

## 🧬 Agent Capabilities

### HLA Teacher Agent
- Educational Q&A about HLA and MHC
- Web search integration
- RAG-powered knowledge base queries
- MCP server utilization

### HLA Imputation Agent
- Statistical HLA typing from SNP data
- Multiple imputation algorithms
- Quality assessment and validation

### HLA Fine Mapping Agent
- Association analysis
- Conditional analysis workflows
- Statistical modeling

### Genotype Phasing Agent
- Haplotype reconstruction
- Phase inference algorithms
- Population-specific models

### File Converter Agent
- Multiple format support
- Data transformation utilities
- Quality control checks

### Parameter Handler Agent
- Configuration management
- Parameter validation
- Workflow optimization

## Example Data

### Example Data for HLA Imputation

1. `https://github.com/WansonChoi/CookHLA/tree/master/example`
2. `https://github.com/FRED-2/OptiType/tree/master/test/exome`

### Example Data for HLA Fine-Mapping

`https://github.com/WansonChoi/HATK/tree/master/example`

### LLM Evaluation Code & Data

`https://github.com/dhkwnr97/Sim_LLMAns_Ref`

### BEAGEL Tools

`https://faculty.washington.edu/browning/beagle_utilities/utilities.html`

## 🔍 Troubleshooting

### Common Issues

1. **Ollama Connection**: Ensure Ollama server is running(you can use another console window: $ollama serve)
2. **Environment Variables**: Verify `.env` file configuration
3. **Dependencies**: Confirm all packages installed correctly
4. **MCP Servers**: Check server configurations and API keys

### Logs

Check application logs in:
- `data/logs/ollama.log` - Ollama server logs
- Console output for agent interactions

---

*HLAgent - Advancing HLA research through intelligent ai agent natural language chatting and processing* 🧬