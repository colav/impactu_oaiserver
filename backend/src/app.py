from fastapi import FastAPI, Query, Request
from fastapi.responses import Response, JSONResponse
from .oai import handle_oai, OAI_COLLECTIONS
from .mongo_client import get_db
import os
import uvicorn
import argparse
import logging
import traceback
from xml.sax.saxutils import escape

app = FastAPI()


@app.get("/oai")
def oai_endpoint(
    request: Request,
    verb: str = Query(None),
    metadataPrefix: str = Query(None),
    resumptionToken: str = Query(None),
    pageSize: int = Query(None),
    identifier: str = Query(None),
    set: str = Query(None),
):
    args = {
        "verb": verb,
        "metadataPrefix": metadataPrefix,
        "resumptionToken": resumptionToken,
        "pageSize": pageSize,
        "identifier": identifier,
        "set": set,
    }
    args = {k: v for k, v in args.items() if v is not None}
    try:
        # pass the effective request base URL to the OAI handler so Identify returns matching base
        # prefer X-Forwarded-Host when behind our proxy so Identify/baseURL match proxy
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        scheme = request.url.scheme
        base = f"{scheme}://{host}{request.url.path}"
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
