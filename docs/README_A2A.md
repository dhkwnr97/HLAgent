# HLAgent A2A Protocol Integration

This document describes how HLAgent integrates with Google's Agent-to-Agent (A2A) protocol, enabling interoperability with external A2A-compatible systems.

## Overview

HLAgent now supports the A2A protocol, allowing external clients to communicate with the HLAgent multi-agent system through a standardized interface. This enables HLAgent to be integrated into larger agent ecosystems and provides an alternative to the Streamlit web interface.

## Architecture

### A2A Components

- **A2A Server** (`src/a2a/server.py`): Exposes HLAgent's supervisor agent as an A2A-compatible server
- **A2A Client** (`src/a2a/client.py`): Interactive command-line client for communicating with HLAgent
- **Agent Card** (`config/agent_card_HLAgent.json`): Describes HLAgent's capabilities and interface

### Multi-Agent Structure

HLAgent's A2A integration maintains the existing multi-agent architecture:

```
┌─────────────────┐                     ┌──────────────────────────────────────────────────────────┐
│                 │                     │                       "HLAgent"                          │
│                 │     A2A Protocol    │                  ┌──────────────────┐                    │
│   A2A Client    │◄───────────────────►│                  │    Supervisor    │                    │
│                 │                     │                  │      Agent       │                    │
│                 │                     │                  │                  │                    │
└─────────────────┘                     │                  └─────────┬────────┘                    │
                                        │                            │                             │   
                                        │                            │ Handover                    │
                                        │                            ▼                             │
                                        │     ┌──────────────────────────────────────────────┐     │
                                        │     │                Sub-Agents                    │     │
                                        │     ├──────────────┬─────────────┬─────────────────┤     │
                                        │     │ HLA Teacher  │File Convert │Genotype Phasing │     │
                                        │     ├──────────────┼─────────────┼─────────────────┤     │
                                        │     │HLA Imputation│HLA Fine Map │Parameter Handler│     │
                                        │     └──────────────┴─────────────┴─────────────────┘     │     
                                        └──────────────────────────────────────────────────────────┘
```

## Usage

### Starting the A2A Server

```bash
# Direct execution
python src/a2a/server.py
```

### Using the A2A Client (Another console window)

```bash
# Start the interactive client
python src/a2a/client.py
```

### Example Conversation Flow

```
👤 You [supervisor]: I want to see hla teacher agent
🤖 HLAgent: Supervisor agent handover to HLA teacher agent.

👤 You [hlateacher]: What is HLA?
🤖 HLAgent: HLA (Human Leukocyte Antigen) is a complex of genes located on chromosome 6...

👤 You [hlateacher]: What is MHC?
🤖 HLAgent: MHC (Major Histocompatibility Complex) is the genetic region that contains HLA genes...

👤 You [hlateacher]: Done!
🤖 HLAgent: Back to supervisor agent.

👤 You [supervisor]: A2Aexit
🤖 HLAgent: Goodbye! Exiting A2A client.
```

## Available Commands

### Agent Navigation
- `"I want to see hla teacher agent"` - Switch to HLA education agent
- `"Done!"` - Return to supervisor agent
- `"A2Aexit"` - Exit the A2A client

### Agent Capabilities

#### Supervisor Agent
- **Role**: Main entry point, orchestrates multi-agent workflows
- **Capabilities**: Agent delegation, workflow coordination, general assistance

#### HLA Teacher Agent  
- **Role**: Educational resource for HLA and immunogenetics
- **Capabilities**: HLA system explanation, MHC education, immunogenetics concepts

## Configuration

### Environment Variables

Create a `.env` file with required API keys:

```bash
# Required for LLM providers
GOOGLE_API_KEY=your_google_api_key

# Optional: Custom model configurations
# modify .env file 
DEFAULT_LLM_PROVIDER=google
DEFAULT_LLM_MODEL=gemini-2.0-flash
```

### Agent Card Configuration

The agent card (`config/agent_card_HLAgent.json`) defines HLAgent's capabilities for A2A discovery:

- **Name**: HLAgent
- **Description**: HLA multi-agent genomic analysis system
- **Skills**: 6 specialized capabilities across genomic analysis workflow
- **URL**: http://localhost:8995 (configurable)
- **Protocol Version**: 1.0.0

## Integration Examples

### Python A2A Client Integration

```python
import asyncio
from src.a2a.client import HLAgentA2AClient

async def example_integration():
    client = HLAgentA2AClient("http://localhost:8995")
    
    # Send a message
    response = await client.send_message("I want to see hla teacher agent")
    print(f"Agent: {response}")
    
    # Continue conversation
    response = await client.send_message("What is HLA?")
    print(f"Agent: {response}")

# Run the example
asyncio.run(example_integration())
```

### External A2A Client Integration

Any A2A-compatible client can connect to HLAgent:

```python
from fasta2a.client import A2AClient
from fasta2a.schema import Message, TextPart
import uuid

async def external_client_example():
    client = A2AClient("http://localhost:8995")
    
    message = Message(
        role='user',
        kind='message',
        message_id=str(uuid.uuid4()),
        context_id=str(uuid.uuid4()),
        parts=[TextPart(kind='text', text="What can you help me with?")]
    )
    
    response = await client.send_message(message)
    # Handle response...
```

## Troubleshooting

### Common Issues

1. **Server won't start**: Check that all dependencies are installed (`pip install fasta2a pydantic-ai`)
2. **Client connection failed**: Ensure server is running on specified port
3. **Agent handover not working**: Check supervisor agent tools are properly configured
4. **Environment variables**: Ensure `.env` file contains required API keys

## Future Enhancements

- **Authentication**: Implement security schemes for production use
- **Multi-context**: Support multiple concurrent conversations
- **Agent Discovery**: Dynamic agent capability advertisement
- **Performance Monitoring**: A2A-specific metrics and monitoring

## License

HLAgent A2A integration follows the same license as the main HLAgent project.