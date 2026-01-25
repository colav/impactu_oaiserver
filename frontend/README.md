Frontend (Next.js + Ant Design)

Build & export static site:

```bash
cd frontend
npm install
npm run build
# exported static files will be in frontend/out
```

The backend serves `frontend/out/index.html` for `/` and when a browser visits `/oai` without OAI query params.

Development (hot reload)

```bash
cd frontend
npm install
# Start Next.js dev server (hot reload on changes)
npm run dev
# Dev server runs on http://localhost:3000 by default. The dev server is configured to proxy
# `/oai` requests to the backend at http://localhost:8000 so you can use the same client-side paths.
```
