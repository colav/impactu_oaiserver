from fastapi import FastAPI, Query
from fastapi.responses import Response, JSONResponse
from .oai import handle_oai, OAI_COLLECTIONS
from .mongo_client import get_db
import os
import uvicorn

app = FastAPI()


@app.get("/oai")
def oai_endpoint(
    verb: str = Query(None),
    metadataPrefix: str = Query(None),
    resumptionToken: str = Query(None),
    pageSize: int = Query(None),
    identifier: str = Query(None),
):
    # Use FastAPI query parameters; pass args dict-like to handler
    args = {
        "verb": verb,
        "metadataPrefix": metadataPrefix,
        "resumptionToken": resumptionToken,
        "pageSize": pageSize,
        "identifier": identifier,
    }
    # remove None values
    args = {k: v for k, v in args.items() if v is not None}
    xml = handle_oai(args)
    return Response(content=xml, media_type="application/xml")


@app.get("/stats")
def stats():
    """Return counts per collection for the collections served by the OAI endpoints."""
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.app:app", host="0.0.0.0", port=port, reload=True)
