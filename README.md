# OAI-PMH CERIF Server (Python)

Minimal OAI-PMH server that reads records from a MongoDB database named `kahi` and serves metadata in a minimal CERIF XML structure.

Quick start

1. Create a Python venv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure MongoDB connection (optional):

```bash
export MONGO_URI="mongodb://localhost:27017"
export DB_NAME="kahi"
```

3. Run the server (FastAPI + Uvicorn):

```bash
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

4. Example requests:

- Identify: `http://localhost:8000/oai?verb=Identify`
- ListRecords: `http://localhost:8000/oai?verb=ListRecords&metadataPrefix=cerif`

Notes
- This is a minimal scaffold meant for development and extension. CERIF output is intentionally simple; adapt mapping in `src/cerif.py` to match your desired CERIF schema.
