# Sellcx Backend API

## Overview

This application is designed to streamline both Q&A and appointment scheduling through a powerful Agent Management Architecture (AMA) that leverages agent execution. It seamlessly integrates with Google Calendar for booking, viewing, and managing appointments. Additionally, the application features an advanced knowledge base powered by a Neo4j database, enabling efficient Q&A through retrieval from a knowledge graph. By utilizing LangChain and LangGraph, it ensures precise natural language processing and graph-based workflows for smooth scheduling. Managed with Poetry, the application guarantees seamless dependency handling and environment setup.

## Video Demo 
https://www.dropbox.com/scl/fi/ewvf6scp2qcp8dw132c2l/agents_demo.mp4?rlkey=uzekf7phh9ujyake575pk25g5&st=gg7xmoos&dl=0

## Deprecated Version Access 
- **Link** : https://highlandcontractors.sell.cx/
- **Username** : highlandcontractors
- **Password** : ywL2U2ZJR8ukkpls

## Features

- **Agent Management Architecture (AMA)**: Core architecture supporting multiple agent types (support, appointment, retrieval) with minimal setup
- **Voice Integration**: Advanced voice processing with topic detection and transition management
- **Authorization System**: Basic authorization framework with agent-specific permissions
- **Retrieval from KG**: Included retrieval from Knowledge Graph to enable Q&A based on the knowledgebase in Neo4J database
- **Google Calendar Integration**: Connects and interacts with Google Calendar to book, view, and manage appointments
- **Neo4j Database**: Integrated for creating knowledgebase
- **LangChain/LangGraph**: Utilizes advanced natural language processing and graph-based workflows for efficient scheduling
- **Poetry Package Management**: Ensures smooth dependency management and environment setup
- **Dual Application Structure**: Supports both API (FastAPI) and Voice applications with shared utilities
- **Common Utilities**: Centralized utility functions for configuration, session management, and API key handling
- **Performance Monitoring**: Integrated Langsmith tracing for token usage and performance evaluation with VOIP and EW

## Version Requirements

### Base Requirements

- Python: ^3.11
- Poetry: Latest version

### Package Dependencies

```
langchain = ">=0.3.15,<1.0"
langgraph = "0.2.65"
langchain-openai = "^0.3.1"
langchain-experimental = "^0.3.4"
fastapi = "^0.114.2"
streamlit = "^1.41.1"
pydantic = "^2.10.6"
neo4j = "^5.27.0"
redis = "^5.0.8"
google-api-python-client = "^2.137.0"
google-auth-httplib2 = "^0.2.0"
google-auth-oauthlib = "^1.2.1"
livekit = "^0.16.2"
livekit-agents = "^0.8.12"
livekit-plugins-openai = "^0.8.3"
livekit-plugins-deepgram = "^0.6.7"
livekit-plugins-silero = "^0.6.4"
livekit-plugins-elevenlabs = "^0.7.4"
twilio = "^9.2.4"
elevenlabs = "^1.7.0"
```

## Prerequisites

- Google Cloud account with Google Calendar API enabled
- Neo4j database (local or cloud-based)
- Redis server (for session management)
- OpenAI API key
- Deepgram API key (for voice recognition)
- ElevenLabs API key (for text-to-speech, optional)
- Langsmith API key (for performance monitoring)

## Installation

1. **Clone the repository**:
   ```sh
   git clone https://github.com/SellCX/backend.git
   cd backend
   ```

2. **Installing Dependencies***

1.  **Install Poetry**:\
    Follow the [official Poetry installation guide](https://python-poetry.org/docs/#installation) if you don't have it installed already.

2.  **Install dependencies**:

      ```
      poetry install
      ```
3.  **Activate Shell**:

      ```
      poetry shell
      ```
---
4. **Set up Google Calendar API credentials**:

   - Create a project in the [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the [Google Calendar API](https://console.cloud.google.com/flows/enableapi?apiid=calendar)
   - Go to the [Credentials](https://console.cloud.google.com/apis/credentials) page
   - Click on **Create Credentials** and select **OAuth Client ID**
   - Then select application type as **Desktop app**
   - Configure the OAuth consent screen with the required details
   - After creating the OAuth client, download the JSON file
   - Save the JSON file in a `.credentials` folder in the root directory of the project with the name `google.json`
   - Ensure to update the calendar id in main `config.json` file and for supported experts config

5. **Set up Neo4j Database credentials**:

   - Ensure that you have a running instance of Neo4j (local or cloud-based)
   - Update the .env file in #Neo4j section with your Neo4j credentials as follows (ex. for Highland contractors):

     Replace `<neo4j connection uri>`, your_username, your_password & <smb:hiland contractor> with your actual Neo4j connection details.

6. **Set up Redis**:

   - Install Redis on your system or use a cloud-based Redis service
   - Update the `.env` file in the #Redis section with your Redis connection details:

7. **Set up environment variables**:
   - Rename `.env.example` to `.env`:
     ```sh
     cp .env.example .env
     ```
   - Update the `.env` file with the necessary environment variables:

## Usage

1. **For linux , Windows(WSL) and Mac users**:
   ```sh
   ./start.sh
   ```
1. **For windows users**:
   ```sh
   ./start.ps1
   ```

## Configuration

The application requires several configuration components:

### Basic Configuration

- `google.json` file in the `.credentials` directory for Google Calendar API authentication
- `.env` file with all required API keys and connection details
- Neo4j and Redis connection details in the configuration or environment variables

### Agent Configuration

- Support agent configuration for Q&A handling
- Appointment agent setup for calendar management
- Retrieval agent configuration for knowledge graph access
- Authorization agent setup for security management

### Voice Integration Setup

- Topic detection configuration
- Dialog management settings
- Voice response formatting
- State configuration for voice contexts

### Performance Monitoring Setup

- Langsmith tracing configuration for token usage tracking
- Performance metrics collection for VOIP calls
- EW (Enterprise Workflow) performance monitoring
- Integration with Langsmith dashboard

The application will use these configurations to authenticate with various services and manage sessions.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License


All rights reserved by GenerexAI



