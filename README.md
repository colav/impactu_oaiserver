# OAI-PMH CERIF Server (Python)
# OAI-PMH CERIF Server (Python)

Minimal OAI-PMH server that reads records from a MongoDB database and serves metadata in a CERIF-like XML structure.

Quick start

1. Create a Python venv and install the package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. Configure MongoDB connection (optional):

```bash
export MONGO_URI="mongodb://localhost:27017"
export DB_NAME="kahi"
```

3. Run the server using the installed console script:

```bash
impactu_oaiserver
```

4. Example requests:

- Identify: `http://localhost:8000/oai?verb=Identify`
- ListRecords: `http://localhost:8000/oai?verb=ListRecords&metadataPrefix=cerif`

Notes
- To run directly during development without installing, use `uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload`.
