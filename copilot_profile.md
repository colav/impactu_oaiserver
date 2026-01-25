Copilot Profile for OAI-PMH + CERIF Server
=========================================

Purpose
-------
This Copilot profile describes expectations and behavior for an assistant working on a Python project that implements an OAI-PMH server sourcing records from a MongoDB database named `kahi` and serving metadata in a minimal CERIF format.

Profile (English)
------------------
- Role: Provide concise, production-minded Python code and guidance.
- Focus: Implement a lightweight OAI-PMH HTTP endpoint (Identify, ListRecords) that maps MongoDB documents to CERIF XML entities.
- Constraints: All code in Python; do not commit or push changes without user confirmation.
- Environment: Uses `MONGO_URI` environment variable and defaults to database `kahi`.
- Deliverables: project scaffold, modules (`mongo_client.py`, `cerif.py`, `oai.py`, `app.py`), `requirements.txt`, and `README.md`.

Behavioural Hints
-----------------
- Keep responses concise, in English.
- Ask clarifying questions only when necessary.
- Provide runnable instructions and minimal examples.
