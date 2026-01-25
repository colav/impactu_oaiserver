from lxml import etree
import os
from .mongo_client import get_db
from .cerif import doc_to_cerif_element
import datetime
from typing import Optional, Dict, Any
import json
import base64


def _format_datestamp(raw):
    if raw is None:
        return ""
    try:
        if isinstance(raw, (int, float)) or (isinstance(raw, str) and raw.isdigit()):
            import datetime as _dt

            epoch = int(raw)
            return _dt.datetime.utcfromtimestamp(epoch).isoformat() + "Z"
    except Exception:
        pass
    try:
        if isinstance(raw, str) and ("T" in raw or "-" in raw):
            return raw if raw.endswith("Z") else raw + "Z"
    except Exception:
        pass
    return ""


OAI_NS = "http://www.openarchives.org/OAI/2.0/"

REPO_IDENTIFIER = "impactu.colav.co"

BASE_URL = os.environ.get("OAI_BASE_URL", "http://localhost:8000/oai")

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
    request.text = BASE_URL
    identify = etree.SubElement(root, "Identify")
    repoName = etree.SubElement(identify, "repositoryName")
    repoName.text = "Impactu OAI-PMH CERIF"
    baseURL = etree.SubElement(identify, "baseURL")
    baseURL.text = BASE_URL
    protocolVersion = etree.SubElement(identify, "protocolVersion")
    protocolVersion.text = "2.0"
    adminEmail = etree.SubElement(identify, "adminEmail")
    adminEmail.text = "grupocolav@udea.edu.co"
    earliestDatestamp = etree.SubElement(identify, "earliestDatestamp")
    earliestDatestamp.text = "2000-01-01T00:00:00Z"
    deletedRecord = etree.SubElement(identify, "deletedRecord")
    deletedRecord.text = "no"
    granularity = etree.SubElement(identify, "granularity")
    granularity.text = "YYYY-MM-DDThh:mm:ssZ"
    desc = etree.SubElement(identify, "description")
    oi_ns = "http://www.openarchives.org/OAI/2.0/oai-identifier"
    oai_id = etree.SubElement(desc, "{" + oi_ns + "}oai-identifier")
    s = etree.SubElement(oai_id, "{" + oi_ns + "}scheme")
    s.text = "oai"
    repo_id = etree.SubElement(oai_id, "{" + oi_ns + "}repositoryIdentifier")
    repo_id.text = REPO_IDENTIFIER
    delimiter = etree.SubElement(oai_id, "{" + oi_ns + "}delimiter")
    delimiter.text = ":"
    sample = etree.SubElement(oai_id, "{" + oi_ns + "}sampleIdentifier")
    sample.text = f"oai:{REPO_IDENTIFIER}:12345"
    desc2 = etree.SubElement(identify, "description")
    openaire_ns = "https://www.openaire.eu/cerif-profile/1.2/"
    service = etree.SubElement(desc2, "{" + openaire_ns + "}Service", id="Service")
    acronym = etree.SubElement(service, "{" + openaire_ns + "}Acronym")
    acronym.text = REPO_IDENTIFIER
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _doc_header(record_el, collection: str, doc: dict):
    header = etree.SubElement(record_el, "header")
    identifier = etree.SubElement(header, "identifier")
    identifier.text = f"oai:{REPO_IDENTIFIER}:{doc.get('_id')}"
    datestamp = etree.SubElement(header, "datestamp")
    raw = (doc.get("updated") or [{}])[-1].get("time") if isinstance(doc.get("updated"), list) and doc.get("updated") else doc.get("date") or doc.get("year") or None
    datestamp.text = _format_datestamp(raw)


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


def ListRecords_with_pagination(db, metadataPrefix: str = "cerif", resumptionToken: Optional[str] = None, pageSize: int = 100, setSpec: Optional[str] = None):
    state = {"coll_index": 0, "last_id": None, "served": 0}
    if resumptionToken:
        dec = _decode_token(resumptionToken)
        if isinstance(dec, dict):
            state.update(dec)
    start_index = int(state.get("coll_index", 0))
    last_id = state.get("last_id")
    served = int(state.get("served") or 0)
    # validation limit across the whole harvest (0 = unlimited)
    try:
        validation_limit = int(os.environ.get("OAI_VALIDATION_LIMIT", "0") or 0)
    except Exception:
        validation_limit = 0

    root = _oai_root()
    responseDate = etree.SubElement(root, "responseDate")
    responseDate.text = datetime.datetime.utcnow().isoformat() + "Z"
    request = etree.SubElement(root, "request")
    request.text = BASE_URL
    listRecords = etree.SubElement(root, "ListRecords")

    set_to_col = {
        "openaire_cris_publications": ["works"],
        "openaire_cris_products": ["sources"],
        "openaire_cris_patents": ["patents"],
        "openaire_cris_persons": ["person"],
        "openaire_cris_orgunits": ["affiliations"],
        "openaire_cris_projects": ["projects"],
        "openaire_cris_funding": [],
        "openaire_cris_events": ["events"],
        "openaire_cris_equipments": [],
    }
    allowed_collections = None
    if setSpec:
        allowed_collections = set_to_col.get(setSpec)
    coll_idx = start_index
    remaining = pageSize
    if validation_limit > 0:
        remaining = min(remaining, max(0, validation_limit - served))
        if remaining <= 0:
            # return empty ListRecords with no resumptionToken
            return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    last_seen = None
    while coll_idx < len(OAI_COLLECTIONS) and remaining > 0:
        coll_name = OAI_COLLECTIONS[coll_idx]
        if allowed_collections is not None and coll_name not in allowed_collections:
            coll_idx += 1
            last_id = None
            continue
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
            cerif_el = doc_to_cerif_element(doc, collection=coll_name, metadataPrefix=metadataPrefix)
            metadata.append(cerif_el)
            last_seen = (coll_name, doc.get("_id"))
            served += 1
            # stop early if we've hit the validation limit
            if validation_limit > 0 and served >= validation_limit:
                break
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
        # include served count in the resumption token so the validation limit is enforced across pages
        next_state["served"] = served
        token = _encode_token(next_state)
        rt = etree.SubElement(listRecords, "resumptionToken")
        rt.text = token

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def ListIdentifiers_with_pagination(db, resumptionToken: Optional[str] = None, pageSize: int = 100):
    state = {"coll_index": 0, "last_id": None, "served": 0}
    if resumptionToken:
        dec = _decode_token(resumptionToken)
        if isinstance(dec, dict):
            state.update(dec)
    start_index = int(state.get("coll_index", 0))
    last_id = state.get("last_id")
    served = int(state.get("served") or 0)
    try:
        validation_limit = int(os.environ.get("OAI_VALIDATION_LIMIT", "0") or 0)
    except Exception:
        validation_limit = 0

    root = _oai_root()
    responseDate = etree.SubElement(root, "responseDate")
    responseDate.text = datetime.datetime.utcnow().isoformat() + "Z"
    request = etree.SubElement(root, "request")
    request.text = BASE_URL
    listIds = etree.SubElement(root, "ListIdentifiers")

    coll_idx = start_index
    remaining = pageSize
    if validation_limit > 0:
        remaining = min(remaining, max(0, validation_limit - served))
        if remaining <= 0:
            return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
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
            raw = (doc.get("updated") or [{}])[-1].get("time") if isinstance(doc.get("updated"), list) and doc.get("updated") else doc.get("date") or None
            datestamp.text = _format_datestamp(raw)
            last_seen = (coll_name, doc.get("_id"))
            served += 1
            if validation_limit > 0 and served >= validation_limit:
                break
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
        next_state["served"] = served
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
    request.text = BASE_URL
    record = etree.SubElement(root, "record")
    _doc_header(record, collection, doc)
    metadata = etree.SubElement(record, "metadata")
    metadata.append(doc_to_cerif_element(doc, collection=collection, metadataPrefix=metadataPrefix))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def handle_oai(args):
    verb = args.get("verb")
    if verb == "Identify":
        return identify()
    elif verb == "ListMetadataFormats":
        root = _oai_root()
        responseDate = etree.SubElement(root, "responseDate")
        responseDate.text = datetime.datetime.utcnow().isoformat() + "Z"
        request = etree.SubElement(root, "request")
        request.text = BASE_URL
        lm = etree.SubElement(root, "ListMetadataFormats")
        mf1 = etree.SubElement(lm, "metadataFormat")
        mp1 = etree.SubElement(mf1, "metadataPrefix")
        mp1.text = "oai_cerif_openaire_1.2"
        schema1 = etree.SubElement(mf1, "schema")
        schema1.text = "https://www.openaire.eu/schema/cris/1.2/openaire-cerif-profile.xsd"
        mn1 = etree.SubElement(mf1, "metadataNamespace")
        mn1.text = "https://www.openaire.eu/cerif-profile/1.2/"
        mf2 = etree.SubElement(lm, "metadataFormat")
        mp2 = etree.SubElement(mf2, "metadataPrefix")
        mp2.text = "oai_cerif_openaire_1.1.1"
        schema2 = etree.SubElement(mf2, "schema")
        schema2.text = "https://www.openaire.eu/schema/cris/1.1.1/openaire-cerif-profile.xsd"
        mn2 = etree.SubElement(mf2, "metadataNamespace")
        mn2.text = "https://www.openaire.eu/cerif-profile/1.1.1/"
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    elif verb == "ListSets":
        root = _oai_root()
        responseDate = etree.SubElement(root, "responseDate")
        responseDate.text = datetime.datetime.utcnow().isoformat() + "Z"
        request = etree.SubElement(root, "request")
        request.text = "http://localhost:8000/oai"
        ls = etree.SubElement(root, "ListSets")
        sets = [
            ("openaire_cris_publications", "OpenAIRE_CRIS_publications"),
            ("openaire_cris_products", "OpenAIRE_CRIS_products"),
            ("openaire_cris_patents", "OpenAIRE_CRIS_patents"),
            ("openaire_cris_persons", "OpenAIRE_CRIS_persons"),
            ("openaire_cris_orgunits", "OpenAIRE_CRIS_orgunits"),
            ("openaire_cris_projects", "OpenAIRE_CRIS_projects"),
            ("openaire_cris_funding", "OpenAIRE_CRIS_funding"),
            ("openaire_cris_events", "OpenAIRE_CRIS_events"),
            ("openaire_cris_equipments", "OpenAIRE_CRIS_equipments"),
        ]
        for spec, name in sets:
            s = etree.SubElement(ls, "set")
            ss = etree.SubElement(s, "setSpec")
            ss.text = spec
            sn = etree.SubElement(s, "setName")
            sn.text = name
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    elif verb == "ListRecords":
        token = args.get("resumptionToken")
        pageSize = int(args.get("pageSize") or 100)
        setSpec = args.get("set")
        db = get_db()
        return ListRecords_with_pagination(db, args.get("metadataPrefix", "cerif"), token, pageSize, setSpec)
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
        responseDate = etree.SubElement(root, "responseDate")
        responseDate.text = datetime.datetime.utcnow().isoformat() + "Z"
        request = etree.SubElement(root, "request")
        request.text = BASE_URL
        error = etree.SubElement(root, "error")
        error.set("code", "badVerb")
        error.text = "Bad verb or not implemented"
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
