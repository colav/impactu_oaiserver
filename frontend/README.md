Frontend (Next.js + Ant Design)

Build & export static site:

```bash
cd frontend
npm install
npm run build
# exported static files will be in frontend/out
```

The backend serves `frontend/out/index.html` for `/` and when a browser visits `/oai` without OAI query params.
