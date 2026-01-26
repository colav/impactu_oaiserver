from fastapi import FastAPI, Query, Request
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .oai import handle_oai, OAI_COLLECTIONS
from .mongo_client import get_db
import os
import uvicorn
import argparse
import logging
import traceback
from xml.sax.saxutils import escape

app = FastAPI()

# Security warning: ensure this path is correct in your deployment image
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "out"))
if os.path.exists(static_dir):
    app.mount("/_next", StaticFiles(directory=os.path.join(static_dir, "_next")), name="next_static")
    # Also mount public/media if it exists in the build output
    media_dir = os.path.join(static_dir, "media")
    if os.path.exists(media_dir):
        app.mount("/media", StaticFiles(directory=media_dir), name="media_static")

import logging as _logging
_logging.basicConfig(level=_logging.INFO)


@app.get("/oai")
def oai_endpoint(
    request: Request,
    verb: str = Query(None),
    metadataPrefix: str = Query(None),
    resumptionToken: str = Query(None),
    pageSize: int = Query(None),
    identifier: str = Query(None),
    set: str = Query(None),
    from_date: str = Query(None, alias="from"),
    until_date: str = Query(None, alias="until"),
):
    args = {
        "verb": verb,
        "metadataPrefix": metadataPrefix,
        "resumptionToken": resumptionToken,
        "pageSize": pageSize,
        "identifier": identifier,
        "set": set,
        "from": from_date,
        "until": until_date,
    }
    args = {k: v for k, v in args.items() if v is not None}
    try:
        # pass the effective request base URL to the OAI handler so Identify returns matching base
        # prefer X-Forwarded-Host when behind our proxy so Identify/baseURL match proxy
        xf = request.headers.get("x-forwarded-host")
        host_hdr = request.headers.get("host")
        host = xf or host_hdr
        scheme = request.url.scheme
        base = f"{scheme}://{host}{request.url.path}"
        _logging.info(f"OAI incoming headers: X-Forwarded-Host={xf!r}, Host={host_hdr!r}")
        _logging.info(f"Computed base URL for OAI responses: {base}")
        # If this is a browser request (Accept: text/html) and there are no OAI args,
        # serve the frontend SPA so humans see the UI at /oai. Otherwise return OAI XML.
        accept = request.headers.get("accept", "")
        if not args and "text/html" in accept.lower():
            # try to return frontend-built index
            frontend_index = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "out", "index.html")
            )
            if os.path.exists(frontend_index):
                return FileResponse(frontend_index, media_type="text/html")
        xml = handle_oai(args, base_url=base)
        return Response(content=xml, media_type="application/xml")
    except Exception as e:
        # log full traceback and return a valid OAI-PMH XML error response
        logging.exception("Unhandled error in OAI endpoint")
        tb = traceback.format_exc()
        logging.error(tb)
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
            "<error>"
            + escape(str(e))
            + "</error>"
            + "</OAI-PMH>"
        )
        return Response(content=body, media_type="application/xml", status_code=500)


@app.get("/stats")
def stats():
    db = get_db()
    out = {}
    total = 0
    for coll in OAI_COLLECTIONS:
        if coll in db.list_collection_names():
            n = int(db[coll].estimated_document_count())
        else:
            n = 0
        out[coll] = n
        total += n
    out["total"] = total
    return JSONResponse(out)


def _frontend_index_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "out", "index.html"))


@app.get("/")
def root():
    idx = _frontend_index_path()
    if os.path.exists(idx):
        return FileResponse(idx, media_type="text/html")
    return JSONResponse({"status": "backend running"})


@app.get("/{full_path:path}")
def catch_all(full_path: str, request: Request):
    # Try to serve a specific file from the static index if it exists
    out_dir = os.path.dirname(_frontend_index_path())
    file_path = os.path.join(out_dir, full_path)
    
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    # Otherwise, handle SPA routing: serve index.html for browser navigations
    accept = request.headers.get("accept", "")
    idx = _frontend_index_path()
    if "text/html" in accept.lower() and os.path.exists(idx):
        return FileResponse(idx, media_type="text/html")
    
    return JSONResponse({"detail": "Not Found"}, status_code=404)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    p.add_argument("--validation", type=int, default=None, help="Limit number of documents served for validation")
    args = p.parse_args()
    port = args.port
    if args.validation is not None:
        os.environ["OAI_VALIDATION_LIMIT"] = str(args.validation)
    uvicorn.run("backend.src.app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
