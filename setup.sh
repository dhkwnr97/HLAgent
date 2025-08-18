#!/bin/bash

# HLAgent Setup Script
# HLA Analysis AI Agent

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}HLAgent - HLA Analysis AI Agent Setup${NC}"
echo -e "${BLUE}=====================================${NC}"

# Function to check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to create directories
create_directories() {
    echo -e "${GREEN}Creating directory structure...${NC}"
    
    # Data directories
    mkdir -p data/input
    mkdir -p data/output/backups
    mkdir -p data/output/BMarkerRegression
    mkdir -p data/output/BMarkerGenerator
    mkdir -p data/output/BMarkerStepwiseRegression
    mkdir -p data/output/HLAImputation
    mkdir -p data/output/ConvertGT
    mkdir -p data/output/ConvertHPED
    mkdir -p data/output/MetaAnalysis
    mkdir -p data/output/NomenCleaner
    mkdir -p data/output/OmnibusTest
    mkdir -p data/output/Phasing
    mkdir -p data/output/Imgt2Seq
    mkdir -p data/reference_panels
    mkdir -p data/sessions

    # Data chroma knowledge
    mkdir -p data/chroma/hla_knowledge
    mkdir -p data/chroma/hla_knowledge_pa
    mkdir -p data/knowledge/Articles

    # Cache and logs
    mkdir -p data/logs
      
    # Create .gitkeep files
    touch data/input/.gitkeep
    touch data/output/backups/.gitkeep
    touch data/output/BMarkerRegression/.gitkeep
    touch data/output/BMarkerGenerator/.gitkeep
    touch data/output/BMarkerStepwiseRegression/.gitkeep
    touch data/output/HLAImputation/.gitkeep
    touch data/output/ConvertGT/.gitkeep
    touch data/output/ConvertHPED/.gitkeep
    touch data/output/MetaAnalysis/.gitkeep
    touch data/output/NomenCleaner/.gitkeep
    touch data/output/OmnibusTest/.gitkeep
    touch data/output/Phasing/.gitkeep
    touch data/output/Imgt2Seq/.gitkeep
    touch data/knowledge/Articles/.gitkeep
    touch data/reference_panels/.gitkeep
    touch data/sessions/.gitkeep
    touch data/logs/.gitkeep
    
    echo -e "${GREEN}✓ Directories created${NC}"
}
# Create directories
create_directories

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Python
if command_exists python3; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
else
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.12+${NC}"
    exit 1
fi

# Check conda/mamba
if command_exists mamba; then
    CONDA_CMD="mamba"
    CONDA_SHELL_HOOK="$(dirname $(which mamba))/../etc/profile.d/conda.sh"
    echo -e "${GREEN}✓ mamba found${NC}"
elif command_exists conda; then
    CONDA_CMD="conda"
    CONDA_SHELL_HOOK="$(conda info --base)/etc/profile.d/conda.sh"
    echo -e "${GREEN}✓ conda found${NC}"
else
    echo -e "${RED}✗ Neither mamba nor conda found${NC}"
    echo "Please install Miniconda or Mamba first:"
    echo "https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Check for mamba
if ! command_exists mamba; then
    echo -e "${YELLOW}Installing mamba...${NC}"
    $CONDA_CMD install -y mamba -c conda-forge
    echo -e "${GREEN}✓ mamba installed${NC}"
else
    echo -e "${GREEN}✓ mamba already installed${NC}"
fi

# Create conda environment
echo -e "${YELLOW}Setting up conda environment...${NC}"

if $CONDA_CMD env list | grep -q "hlagent"; then
    echo -e "${YELLOW}Environment 'hlagent' already exists${NC}"
    read -p "Do you want to update it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Updating environment...${NC}"
        $CONDA_CMD env update -f environment.yml
    fi
else
    echo -e "${GREEN}Creating environment...${NC}"
    $CONDA_CMD env create -f environment.yml
fi

# Activate environment
echo -e "${GREEN}Activating environment...${NC}"
if [ -f "$CONDA_SHELL_HOOK" ]; then
    source "$CONDA_SHELL_HOOK"
else
    eval "$(conda shell.bash hook)"
fi
conda activate hlagent

# Install uv for fast package management
echo -e "${YELLOW}Installing uv package manager...${NC}"
if ! command_exists uv; then
    $CONDA_CMD install -y uv -c conda-forge
    echo -e "${GREEN}✓ uv installed${NC}"
else
    echo -e "${GREEN}✓ uv already installed${NC}"
fi

# Install Python packages with uv
echo -e "${YELLOW}Installing Python packages with uv...${NC}"
uv pip install -r requirements.txt

# Set OLLAMA_MODELS to conda environment-local path
export OLLAMA_MODELS="$CONDA_PREFIX/ollama_models"
mkdir -p "$OLLAMA_MODELS"
echo -e "${GREEN}✓ OLLAMA_MODELS set to $OLLAMA_MODELS${NC}"

# Start Ollama server in background
echo -e "${YELLOW}Starting Ollama server...${NC}"
if ! pgrep -f "ollama serve" > /dev/null; then
    ollama serve > data/logs/ollama.log 2>&1 &
    sleep 5
    if pgrep -f "ollama serve" > /dev/null; then
        echo -e "${GREEN}Ollama server started.${NC}"
    else
        echo -e "${RED}Failed to start Ollama server. Check logs/ollama.log.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}Ollama server already running.${NC}"
fi

# Wait a few seconds for server to start
sleep 5

# Check Ollama
if command_exists ollama; then
    echo -e "${GREEN}✓ Ollama found${NC}"
    echo -e "${YELLOW}Ensuring llama3.1:8b model is available...${NC}"
    if ollama list | grep -q "llama3.1:8b"; then
        echo -e "${GREEN}✓ llama3.1:8b model already present${NC}"
    else
        echo -e "${YELLOW}Downloading llama3.1:8b model...${NC}"
        ollama pull llama3.1:8b
    fi
else
    echo -e "${YELLOW}⚠ Ollama not found${NC}"
    echo "Install Ollama for local LLM support: https://ollama.ai"
    echo "OR Install Ollama through conda: conda install -c conda-forge ollama"
fi

# Check Docker
if command_exists docker; then
    echo -e "${GREEN}✓ Docker found${NC}"
else
    echo -e "${YELLOW}⚠ Docker not found (optional)${NC}"
    echo "Install Docker for CookHLA support"
fi

# Setup .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cp config/.env.example .env 2>/dev/null || cat > .env << EOF
# HLAgent Environment Variables

# API keys (optional)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_API_KEY=your_google_api_key_here

# Ollama settings
OLLAMA_BASE_URL=http://localhost:11434

# MCP settings
MCP_CONFIG_PATH=./config/mcp_config.json

# Data paths
DATA_DIR=./data
INPUT_DIR=./data/input
OUTPUT_DIR=./data/output
LOGS_DIR=./data/logs

EOF
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}Please edit .env to add your API keys${NC}"
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# NPM check for MCP servers
echo -e "${YELLOW}Checking npm for MCP servers...${NC}"
if command_exists npm; then
    echo -e "${GREEN}✓ npm found${NC}"
    
    # Install npx if not available
    if ! command_exists npx; then
        npm install -g npx
    fi
    echo -e "${GREEN}✓ MCP servers ready${NC}"
else
    echo -e "${YELLOW}⚠ npm not found${NC}"
    echo "Install Node.js for MCP server support"
fi

# Summary
echo -e "${BLUE}=====================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}=====================================${NC}"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Edit .env file with choosing LLM provider and your API keys"
echo "2. Run the application: ./run.sh"
echo "3. Access at: http://localhost:8501"

echo -e "\n${YELLOW}Optional:${NC}"
echo "- Install Ollama for local LLM support"
echo "- Get API keys from OpenAI or Anthropic(optional)"

echo -e "\n${GREEN}Happy analyzing! 🧬${NC}"
