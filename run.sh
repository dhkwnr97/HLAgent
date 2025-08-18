#!/bin/bash

# HLAgent Launch Script
# HLA Analysis AI Agent

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Starting HLAgent - HLA Analysis AI Agent...${NC}"

# Check if conda/mamba is installed
if command -v mamba &> /dev/null; then
    CONDA_CMD="mamba"
    CONDA_SHELL_HOOK="$(dirname $(which mamba))/../etc/profile.d/conda.sh"
elif command -v conda &> /dev/null; then
    CONDA_CMD="conda"
    CONDA_SHELL_HOOK="$(conda info --base)/etc/profile.d/conda.sh"
else
    echo -e "${RED}Error: Neither mamba nor conda found. Please install first.${NC}"
    exit 1
fi

# Check if environment exists
if ! $CONDA_CMD env list | grep -q "hlagent"; then
    echo -e "${RED}Error: Environment 'hlagent' not found. Run setup.sh first.${NC}"
    exit 1
fi

# Activate environment if not already active
if [[ "$CONDA_DEFAULT_ENV" != "hlagent" ]]; then
    echo -e "${GREEN}Activating conda environment 'hlagent'...${NC}"
    if [ -f "$CONDA_SHELL_HOOK" ]; then
        source "$CONDA_SHELL_HOOK"
    else
        eval "$(conda shell.bash hook)"
    fi
    conda activate hlagent
else
    echo -e "${GREEN}Conda environment 'hlagent' already active.${NC}"
fi

# Install/update dependencies with mamba if available
#if command -v mamba &> /dev/null; then
#    echo -e "${GREEN}Installing Python dependencies with mamba...${NC}"
#    mamba env update -f environment.yml
#else
#    echo -e "${YELLOW}Installing Python dependencies with conda...${NC}"
#    conda env update -f environment.yml
#fi

# Install/update dependencies with uv if available
#if command -v uv &> /dev/null; then
#    echo -e "${GREEN}Installing Python dependencies with uv...${NC}"
#    uv pip install -r requirements.txt
#else
#    echo -e "${YELLOW}Installing Python dependencies with pip...${NC}"
#    pip install -r requirements.txt
#fi

# Check if Ollama is installed and running
#if command -v ollama &> /dev/null; then
#    if ! pgrep -f "ollama serve" > /dev/null; then
#        echo -e "${YELLOW}Starting Ollama server...${NC}"
#        ollama serve > logs/ollama.log 2>&1 &
#        sleep 5
#        if pgrep -f "ollama serve" > /dev/null; then
#            echo -e "${GREEN}Ollama server started.${NC}"
#        else
#            echo -e "${RED}Failed to start Ollama server. Check logs/ollama.log.${NC}"
#        fi
#    else
#        echo -e "${GREEN}Ollama server already running.${NC}"
#    fi
#else
#    echo -e "${YELLOW}Warning: Ollama not found. Install for local LLM support.${NC}"
#fi

# Check for .env file
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp config/.env.example .env 2>/dev/null || {
        echo -e "${YELLOW}No .env template found. Please run setup.sh first.${NC}"
    }
    echo -e "${YELLOW}Please edit .env file with your API keys${NC}"
fi
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check if HLAGENT_MAIN_DIRECTORY is still the default placeholder
if grep -q '^HLAGENT_MAIN_DIRECTORY=your_hlagent_main_directory_here' .env; then
    echo -e "${YELLOW}HLAGENT_MAIN_DIRECTORY in .env is still set to the default value.\nPlease open the .env file and set HLAGENT_MAIN_DIRECTORY to the absolute path of your HLAgent root folder (e.g., /home/hanjg/App/Agents/HLAgent-main).${NC}"
    exit 1
fi

# Create necessary directories if they don't exist
    # Data directories
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/input
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/backups
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/BMarkerRegression
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/BMarkerGenerator
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/BMarkerStepwiseRegression
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/HLAImputation
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/ConvertGT
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/ConvertHPED
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/MetaAnalysis
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/NomenCleaner
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/OmnibusTest
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/Phasing
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/output/Imgt2Seq
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/reference_panels
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/sessions

    # Data chroma knowledge
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/chroma/hla_knowledge
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/chroma/hla_knowledge_pa
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/knowledge/Articles

    # Cache and logs
    mkdir -p $HLAGENT_MAIN_DIRECTORY/data/logs

# Initialize log file
touch $HLAGENT_MAIN_DIRECTORY/data/logs/hlagent.log

# Run the Streamlit app
echo -e "${GREEN}Launching HLAgent Streamlit app...${NC}"
echo -e "${YELLOW}Access the app at: http://localhost:8501${NC}"
streamlit run $HLAGENT_MAIN_DIRECTORY/src/experience_ui/app.py

# Deactivate on exit
trap "conda deactivate" EXIT
