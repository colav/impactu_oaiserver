<center><img src="https://raw.githubusercontent.com/colav/colav.github.io/master/img/Logo.png"/></center>

# Impactu OAI-PMH CERIF Server

OAI-PMH server implementation for Impactu, serving metadata from MongoDB in CERIF 1.2 XML format. This server supports multi-collection harvesting and implements standard OAI-PMH verbs.

## Core Features
- **CERIF 1.2 Support:** Specialized metadata mapping for CRIS entities (Publications, Persons, Organizations, etc.).
- **Smart Paging:** Persistent resumption tokens that preserve filters across sessions.
- **Cross-Collection Harvesting:** Unified view of multiple MongoDB collections (works, person, affiliations, projects, etc.).
- **OAI Explorer:** Built-in web interface for easy exploration of records and metadata.

## Quick Start

### 1. Environment Setup
Create a Python virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Configuration
Set the following environment variables (defaults provided):

```bash
export MONGO_URI="mongodb://localhost:27017"
export DB_NAME="kahi"
export OAI_BASE_URL="http://localhost:8000/oai"
```

### 3. Run the Server
You can use the console script or run directly with Uvicorn:

```bash
# Using the installed script
impactu_oaiserver

# Or directly with uvicorn for development
uvicorn backend.src.app:app --host 0.0.0.0 --port 8000 --reload
```

## OAI-PMH Endpoint
By default, the OAI endpoint is available at `/oai`. 

Example requests:
- **Identify:** `GET /oai?verb=Identify`
- **List Metadata Formats:** `GET /oai?verb=ListMetadataFormats`
- **List Records (CERIF):** `GET /oai?verb=ListRecords&metadataPrefix=cerif`
- **Filtered by Set:** `GET /oai?verb=ListRecords&metadataPrefix=cerif&set=openaire_cris_publications`

## Frontend Explorer
The project includes a Next.js based UI to browse records.
Navigate to the `frontend/` directory and run:

```bash
npm install
npm run dev
```
Then visit `http://localhost:3000/records`.

## Project Structure
- `backend/src/oai.py`: Core OAI-PMH protocol logic.
- `backend/src/cerif.py`: XML mapping for CERIF 1.2 profiles.
- `frontend/pages/records/`: Record explorer UI.
- `docker/`: Deployment configurations.
