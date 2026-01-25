from lxml import etree
from .mongo_client import get_db
from .cerif import doc_to_cerif_element
import datetime
from typing import Optional, Dict, Any
import json
import base64

OAI_NS = "http://www.openarchives.org/OAI/2.0/"

# Collections served by the OAI-PMH endpoints (order matters for ListRecords)
OAI_COLLECTIONS = [
    "works",
    "patents",
    "events",
    "projects",
    "person",
    "affiliations",
    "sources",
    "subjects",
]


def _oai_root():
    return etree.Element("{%s}OAI-PMH" % OAI_NS, nsmap={None: OAI_NS})


def identify():
    root = _oai_root()
    responseDate = etree.SubElement(root, "responseDate")
    responseDate.text = datetime.datetime.utcnow().isoformat() + "Z"
    request = etree.SubElement(root, "request")
    request.text = "http://localhost:8000/oai"
    identify = etree.SubElement(root, "Identify")
    repoName = etree.SubElement(identify, "repositoryName")
    repoName.text = "kahi OAI-PMH CERIF demo"
    baseURL = etree.SubElement(identify, "baseURL")
    baseURL.text = "http://localhost:8000/oai"
    protocolVersion = etree.SubElement(identify, "protocolVersion")
    protocolVersion.text = "2.0"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _doc_header(record_el, collection: str, doc: dict):
    header = etree.SubElement(record_el, "header")
    identifier = etree.SubElement(header, "identifier")
    identifier.text = f"{collection}:{doc.get('_id')}"
    datestamp = etree.SubElement(header, "datestamp")
    datestamp.text = str((doc.get("updated") or [{}])[-1].get("time") if isinstance(doc.get("updated"), list) and doc.get("updated") else doc.get("date") or doc.get("year") or "")


def _encode_token(state: Dict[str, Any]) -> str:
    safe = {}
    for k, v in state.items():
        if v is None or isinstance(v, (str, int, float, bool)):
            safe[k] = v
        else:
            safe[k] = str(v)
    raw = json.dumps(safe, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_token(token: str) -> Dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        return json.loads(raw)
    except Exception:
        return {}


def ListRecords_with_pagination(db, metadataPrefix: str = "cerif", resumptionToken: Optional[str] = None, pageSize: int = 100):
    state = {"coll_index": 0, "last_id": None}
    if resumptionToken:
        dec = _decode_token(resumptionToken)
        if isinstance(dec, dict):
            state.update(dec)
    start_index = int(state.get("coll_index", 0))
    last_id = state.get("last_id")

    root = _oai_root()
    responseDate = etree.SubElement(root, "responseDate")
    responseDate.text = datetime.datetime.utcnow().isoformat() + "Z"
    request = etree.SubElement(root, "request")
    request.text = "http://localhost:8000/oai"
    listRecords = etree.SubElement(root, "ListRecords")

    coll_idx = start_index
    remaining = pageSize
    last_seen = None
    while coll_idx < len(OAI_COLLECTIONS) and remaining > 0:
        coll_name = OAI_COLLECTIONS[coll_idx]
        if coll_name not in db.list_collection_names():
            coll_idx += 1
            last_id = None
            continue
        coll = db[coll_name]
        query = {}
        if last_id and coll_idx == start_index:
            query = {"_id": {"$gt": last_id}}
        cursor = coll.find(query).sort("_id", 1).limit(remaining)
        docs = list(cursor)
        for doc in docs:
            record = etree.SubElement(listRecords, "record")
            _doc_header(record, coll_name, doc)
            metadata = etree.SubElement(record, "metadata")
            cerif_el = doc_to_cerif_element(doc, collection=coll_name)
            metadata.append(cerif_el)
            last_seen = (coll_name, doc.get("_id"))
        if len(docs) < remaining:
            coll_idx += 1
            last_id = None
            remaining -= len(docs)
        else:
            last_id = docs[-1].get("_id") if docs else last_id
            remaining = 0

    has_more = False
    next_state = None
    if last_seen:
        coll_idx_next = OAI_COLLECTIONS.index(last_seen[0])
        c = last_seen[0]
        if c in db.list_collection_names() and db[c].find_one({"_id": {"$gt": last_seen[1]}}):
            has_more = True
            next_state = {"coll_index": coll_idx_next, "last_id": str(last_seen[1])}
        else:
            for i in range(coll_idx_next + 1, len(OAI_COLLECTIONS)):
                c2 = OAI_COLLECTIONS[i]
                if c2 in db.list_collection_names() and db[c2].find_one():
                    has_more = True
                    next_state = {"coll_index": i, "last_id": None}
                    break

    if has_more and next_state:
        token = _encode_token(next_state)
        rt = etree.SubElement(listRecords, "resumptionToken")
        rt.text = token

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def ListIdentifiers_with_pagination(db, resumptionToken: Optional[str] = None, pageSize: int = 100):
    state = {"coll_index": 0, "last_id": None}
    if resumptionToken:
        dec = _decode_token(resumptionToken)
        if isinstance(dec, dict):
            state.update(dec)
    start_index = int(state.get("coll_index", 0))
    last_id = state.get("last_id")

    root = _oai_root()
    responseDate = etree.SubElement(root, "responseDate")
    responseDate.text = datetime.datetime.utcnow().isoformat() + "Z"
    request = etree.SubElement(root, "request")
    request.text = "http://localhost:8000/oai"
    listIds = etree.SubElement(root, "ListIdentifiers")

    coll_idx = start_index
    remaining = pageSize
    last_seen = None
    while coll_idx < len(OAI_COLLECTIONS) and remaining > 0:
        coll_name = OAI_COLLECTIONS[coll_idx]
        if coll_name not in db.list_collection_names():
            coll_idx += 1
            last_id = None
            continue
        coll = db[coll_name]
        query = {}
        if last_id and coll_idx == start_index:
            query = {"_id": {"$gt": last_id}}
        cursor = coll.find(query).sort("_id", 1).limit(remaining)
        docs = list(cursor)
        for doc in docs:
            header = etree.SubElement(listIds, "header")
            identifier = etree.SubElement(header, "identifier")
            identifier.text = f"{coll_name}:{doc.get('_id')}"
            datestamp = etree.SubElement(header, "datestamp")
            datestamp.text = str((doc.get("updated") or [{}])[-1].get("time") if isinstance(doc.get("updated"), list) and doc.get("updated") else doc.get("date") or "")
            last_seen = (coll_name, doc.get("_id"))
        if len(docs) < remaining:
            coll_idx += 1
            last_id = None
            remaining -= len(docs)
        else:
            last_id = docs[-1].get("_id") if docs else last_id
            remaining = 0

    has_more = False
    next_state = None
    if last_seen:
        coll_idx_next = OAI_COLLECTIONS.index(last_seen[0])
        c = last_seen[0]
        if c in db.list_collection_names() and db[c].find_one({"_id": {"$gt": last_seen[1]}}):
            has_more = True
            next_state = {"coll_index": coll_idx_next, "last_id": str(last_seen[1])}
        else:
            for i in range(coll_idx_next + 1, len(OAI_COLLECTIONS)):
                c2 = OAI_COLLECTIONS[i]
                if c2 in db.list_collection_names() and db[c2].find_one():
                    has_more = True
                    next_state = {"coll_index": i, "last_id": None}
                    break

    if has_more and next_state:
        token = _encode_token(next_state)
        rt = etree.SubElement(listIds, "resumptionToken")
        rt.text = token

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def get_record(identifier: str, metadataPrefix: Optional[str] = "cerif"):
    if ":" not in identifier:
        root = _oai_root()
        err = etree.SubElement(root, "error")
        err.text = "Bad identifier format"
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    collection, docid = identifier.split(":", 1)
    db = get_db()
    if collection not in db.list_collection_names():
        root = _oai_root()
        err = etree.SubElement(root, "error")
        err.text = "Collection not found"
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    doc = db[collection].find_one({"_id": docid})
    if not doc:
        root = _oai_root()
        err = etree.SubElement(root, "error")
        err.text = "Record not found"
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)

    root = _oai_root()
    responseDate = etree.SubElement(root, "responseDate")
    responseDate.text = datetime.datetime.utcnow().isoformat() + "Z"
    request = etree.SubElement(root, "request")
    request.text = "http://localhost:8000/oai"
    record = etree.SubElement(root, "record")
    _doc_header(record, collection, doc)
    metadata = etree.SubElement(record, "metadata")
    metadata.append(doc_to_cerif_element(doc, collection=collection))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def handle_oai(args):
    verb = args.get("verb")
    if verb == "Identify":
        return identify()
    elif verb == "ListRecords":
        token = args.get("resumptionToken")
        pageSize = int(args.get("pageSize") or 100)
        db = get_db()
        return ListRecords_with_pagination(db, args.get("metadataPrefix", "cerif"), token, pageSize)
    elif verb == "GetRecord":
        identifier = args.get("identifier")
        return get_record(identifier, args.get("metadataPrefix", "cerif"))
    elif verb == "ListIdentifiers":
        token = args.get("resumptionToken")
        pageSize = int(args.get("pageSize") or 100)
        db = get_db()
        return ListIdentifiers_with_pagination(db, token, pageSize)
    else:
        root = _oai_root()
        error = etree.SubElement(root, "error")
        error.text = "Bad verb or not implemented"
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
