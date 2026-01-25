from fastapi import FastAPI, Query
from fastapi.responses import Response, JSONResponse
from .oai import handle_oai, OAI_COLLECTIONS
from .mongo_client import get_db
import os
import uvicorn
import logging
import traceback
from xml.sax.saxutils import escape

app = FastAPI()


@app.get("/oai")
def oai_endpoint(
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
        xml = handle_oai(args)
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
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.src.app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
