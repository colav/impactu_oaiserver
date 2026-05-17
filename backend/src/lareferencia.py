"""OAI-PMH endpoint for LaReferencia.

Serves the harvested DSpace records stored in the `oxomoc_colombia` database.
That database holds one `dspace_<acronym>_records` collection per Colombian
institution. Every document has the shape::

    {
      "_id": "oai:<repo-domain>:<handle>",
      "OAI-PMH": { ... }   # the original OAI-PMH GetRecord response, parsed
                           # from XML with xmltodict
    }

Because the record was stored with ``xmltodict``, serving it back is just a
matter of taking ``OAI-PMH.GetRecord.record`` and turning the dict into XML
again with ``xmltodict.unparse``.

This module keeps the same essence as ``oai.py`` (resumption tokens, the same
OAI-PMH verbs) but exposes a separate repository: the metadata format is the
DSpace ``dim`` profile and each institution is published as an OAI set.
"""

from lxml import etree
import os
import json
import base64
import datetime
from typing import Optional, Dict, Any, List

import xmltodict

from .mongo_client import get_lareferencia_db


OAI_NS = "http://www.openarchives.org/OAI/2.0/"
OAI_ID_NS = "http://www.openarchives.org/OAI/2.0/oai-identifier"

REPO_IDENTIFIER = "lareferencia.impactu.colav.co"

BASE_URL = os.environ.get("LAREFERENCIA_BASE_URL", "http://localhost:8000/lareferencia/oai")

# Populated by the HTTP handler so responses echo the URL the client used.
CURRENT_REQUEST_URL: Optional[str] = None

# DSpace Intermediate Metadata — the format every harvested record is stored in.
METADATA_PREFIX = "dim"
METADATA_SCHEMA = "http://www.dspace.org/schema/dim.xsd"
METADATA_NAMESPACE = "http://www.dspace.org/xmlns/dspace/dim"

_RECORDS_SUFFIX = "_records"
_RECORDS_PREFIX = "dspace_"


def _oai_root():
    return etree.Element("{%s}OAI-PMH" % OAI_NS, nsmap={None: OAI_NS})


def _qn(tag: str) -> str:
    """Qualified name in the OAI-PMH namespace."""
    return "{%s}%s" % (OAI_NS, tag)


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _base_skeleton(verb_attrs: Optional[Dict[str, str]] = None):
    """Build an <OAI-PMH> root with <responseDate> and <request>."""
    root = _oai_root()
    etree.SubElement(root, _qn("responseDate")).text = _now()
    request = etree.SubElement(root, _qn("request"))
    request.text = CURRENT_REQUEST_URL or BASE_URL
    if verb_attrs:
        for k, v in verb_attrs.items():
            if v is not None:
                request.set(k, str(v))
    return root


def _error(code: str, message: str, verb_attrs: Optional[Dict[str, str]] = None) -> bytes:
    root = _base_skeleton(verb_attrs)
    err = etree.SubElement(root, _qn("error"))
    err.set("code", code)
    err.text = message
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _serialize(root) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


# --------------------------------------------------------------------------
# Institutions / collections
# --------------------------------------------------------------------------

def _records_collections(db) -> List[str]:
    """Sorted list of `dspace_<acronym>_records` collection names."""
    return sorted(
        name
        for name in db.list_collection_names()
        if name.startswith(_RECORDS_PREFIX) and name.endswith(_RECORDS_SUFFIX)
    )


def _acronym_of(collection_name: str) -> str:
    """`dspace_unaula_records` -> `unaula`."""
    return collection_name[len(_RECORDS_PREFIX):-len(_RECORDS_SUFFIX)]


def _collection_for(acronym: str) -> str:
    return f"{_RECORDS_PREFIX}{acronym}{_RECORDS_SUFFIX}"


def _repository_name(db, acronym: str) -> str:
    """Human-readable name from the institution's `_identity` collection."""
    identity_coll = f"{_RECORDS_PREFIX}{acronym}_identity"
    try:
        if identity_coll in db.list_collection_names():
            doc = db[identity_coll].find_one()
            if doc and doc.get("repository_name"):
                return doc["repository_name"]
    except Exception:
        pass
    return acronym


# --------------------------------------------------------------------------
# Resumption tokens
# --------------------------------------------------------------------------

def _encode_token(state: Dict[str, Any]) -> str:
    raw = json.dumps({k: v for k, v in state.items() if v is not None}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_token(token: str) -> Dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        dec = json.loads(raw)
        return dec if isinstance(dec, dict) else {}
    except Exception:
        return {}


# --------------------------------------------------------------------------
# Record extraction / serialization
# --------------------------------------------------------------------------

def _extract_record(doc: dict) -> Optional[dict]:
    """Pull the `record` dict (header + metadata) out of a stored document."""
    oai = doc.get("OAI-PMH") or {}
    if not isinstance(oai, dict):
        return None
    if isinstance(oai.get("GetRecord"), dict):
        return oai["GetRecord"].get("record")
    if isinstance(oai.get("record"), dict):
        return oai["record"]
    return None


def _datestamp_of(doc: dict) -> str:
    rec = _extract_record(doc) or {}
    header = rec.get("header") or {}
    return header.get("datestamp") or "2000-01-01T00:00:00Z"


def _append_header(record_el, rec: dict):
    """Build an OAI-PMH <header> from the stored record's header dict."""
    src = rec.get("header") or {}
    header = etree.SubElement(record_el, _qn("header"))
    if src.get("@status"):
        header.set("status", str(src["@status"]))
    etree.SubElement(header, _qn("identifier")).text = src.get("identifier") or ""
    etree.SubElement(header, _qn("datestamp")).text = src.get("datestamp") or "2000-01-01T00:00:00Z"
    set_spec = src.get("setSpec")
    if set_spec is not None:
        if not isinstance(set_spec, list):
            set_spec = [set_spec]
        for spec in set_spec:
            # a setSpec may be a plain string or a dict with a '#text' key
            text = spec.get("#text") if isinstance(spec, dict) else spec
            if text:
                etree.SubElement(header, _qn("setSpec")).text = str(text)


def _append_record(parent_el, doc: dict, acronym: str):
    """Append a full OAI-PMH <record> (header + metadata) for a stored document."""
    rec = _extract_record(doc)
    record_el = etree.SubElement(parent_el, _qn("record"))
    if not rec:
        # Malformed document: emit a bare header so harvesting does not break.
        header = etree.SubElement(record_el, _qn("header"))
        etree.SubElement(header, _qn("identifier")).text = str(doc.get("_id") or "")
        etree.SubElement(header, _qn("datestamp")).text = "2000-01-01T00:00:00Z"
        return

    _append_header(record_el, rec)

    # Deleted records carry no metadata.
    if (rec.get("header") or {}).get("@status") == "deleted":
        return

    metadata = rec.get("metadata")
    metadata_el = etree.SubElement(record_el, _qn("metadata"))
    if isinstance(metadata, dict) and metadata:
        try:
            payload_xml = xmltodict.unparse(metadata, full_document=False)
            metadata_el.append(etree.fromstring(payload_xml.encode("utf-8")))
        except Exception:
            # Leave <metadata> empty rather than failing the whole page.
            pass


# --------------------------------------------------------------------------
# Verbs
# --------------------------------------------------------------------------

def identify():
    db = get_lareferencia_db()
    root = _base_skeleton()
    identify = etree.SubElement(root, _qn("Identify"))
    etree.SubElement(identify, _qn("repositoryName")).text = (
        "ImpactU - LaReferencia (Repositorios DSpace de Colombia)"
    )
    etree.SubElement(identify, _qn("baseURL")).text = CURRENT_REQUEST_URL or BASE_URL
    etree.SubElement(identify, _qn("protocolVersion")).text = "2.0"
    etree.SubElement(identify, _qn("adminEmail")).text = "grupocolav@udea.edu.co"
    etree.SubElement(identify, _qn("earliestDatestamp")).text = "2000-01-01T00:00:00Z"
    etree.SubElement(identify, _qn("deletedRecord")).text = "no"
    etree.SubElement(identify, _qn("granularity")).text = "YYYY-MM-DDThh:mm:ssZ"

    desc = etree.SubElement(identify, _qn("description"))
    oai_id = etree.SubElement(desc, "{%s}oai-identifier" % OAI_ID_NS, nsmap={"oai-identifier": OAI_ID_NS})
    etree.SubElement(oai_id, "{%s}scheme" % OAI_ID_NS).text = "oai"
    etree.SubElement(oai_id, "{%s}repositoryIdentifier" % OAI_ID_NS).text = REPO_IDENTIFIER
    etree.SubElement(oai_id, "{%s}delimiter" % OAI_ID_NS).text = ":"
    etree.SubElement(oai_id, "{%s}sampleIdentifier" % OAI_ID_NS).text = (
        "oai:repositorio.example.edu.co:123456789/1"
    )
    return _serialize(root)


def list_metadata_formats():
    root = _base_skeleton({"verb": "ListMetadataFormats"})
    lmf = etree.SubElement(root, _qn("ListMetadataFormats"))
    mf = etree.SubElement(lmf, _qn("metadataFormat"))
    etree.SubElement(mf, _qn("metadataPrefix")).text = METADATA_PREFIX
    etree.SubElement(mf, _qn("schema")).text = METADATA_SCHEMA
    etree.SubElement(mf, _qn("metadataNamespace")).text = METADATA_NAMESPACE
    return _serialize(root)


def list_sets():
    """One OAI set per institution (setSpec = institution acronym)."""
    db = get_lareferencia_db()
    root = _base_skeleton({"verb": "ListSets"})
    ls = etree.SubElement(root, _qn("ListSets"))
    for coll in _records_collections(db):
        acronym = _acronym_of(coll)
        s = etree.SubElement(ls, _qn("set"))
        etree.SubElement(s, _qn("setSpec")).text = acronym
        etree.SubElement(s, _qn("setName")).text = _repository_name(db, acronym)
    return _serialize(root)


def _check_prefix(metadata_prefix: Optional[str], verb_attrs: Dict[str, str]):
    """Return an error response (bytes) if the requested prefix is unsupported."""
    if metadata_prefix and metadata_prefix != METADATA_PREFIX:
        return _error(
            "cannotDisseminateFormat",
            f"Only the '{METADATA_PREFIX}' metadata format is supported",
            verb_attrs,
        )
    return None


def _date_filter(from_arg: Optional[str], until_arg: Optional[str]) -> Dict[str, Any]:
    """Build a Mongo query fragment on the stored record datestamp.

    Datestamps are ISO-8601 strings, which sort lexically, so a plain range
    query works. This path is not indexed, so the filter is best-effort."""
    query: Dict[str, Any] = {}
    rng: Dict[str, str] = {}
    if from_arg:
        rng["$gte"] = from_arg
    if until_arg:
        # extend a bare date to the end of the day so 'until' is inclusive
        rng["$lte"] = until_arg if "T" in until_arg else until_arg + "T23:59:59Z"
    if rng:
        query["OAI-PMH.GetRecord.record.header.datestamp"] = rng
    return query


def _paginate(verb: str, args: Dict[str, Any]):
    """Shared driver for ListRecords and ListIdentifiers.

    Walks the institution collections in order, carrying `(coll_index, last_id)`
    in the resumption token, exactly like `oai.py` walks its CERIF collections."""
    metadata_prefix = args.get("metadataPrefix")
    resumption_token = args.get("resumptionToken")
    set_spec = args.get("set")
    from_arg = args.get("from")
    until_arg = args.get("until")
    try:
        page_size = int(args.get("pageSize") or 200)
    except Exception:
        page_size = 200
    page_size = max(1, min(page_size, 1000))

    verb_attrs = {"verb": verb}

    state: Dict[str, Any] = {"coll_index": 0, "last_id": None, "served": 0}
    if resumption_token:
        dec = _decode_token(resumption_token)
        if not dec:
            return _error("badResumptionToken", "Invalid resumptionToken", verb_attrs)
        state.update(dec)
        # filters travel inside the token across pages
        metadata_prefix = state.get("prefix") or metadata_prefix
        set_spec = state.get("set") or set_spec
        from_arg = state.get("from") or from_arg
        until_arg = state.get("until") or until_arg
    else:
        verb_attrs["metadataPrefix"] = metadata_prefix or METADATA_PREFIX
        if set_spec:
            verb_attrs["set"] = set_spec
        if from_arg:
            verb_attrs["from"] = from_arg
        if until_arg:
            verb_attrs["until"] = until_arg

    prefix_err = _check_prefix(metadata_prefix, verb_attrs)
    if prefix_err is not None:
        return prefix_err

    db = get_lareferencia_db()
    all_colls = _records_collections(db)

    if set_spec:
        target = _collection_for(set_spec)
        if target not in all_colls:
            return _error("badArgument", f"Unknown set '{set_spec}'", verb_attrs)
        colls = [target]
    else:
        colls = all_colls

    coll_index = int(state.get("coll_index") or 0)
    last_id = state.get("last_id")
    served = int(state.get("served") or 0)

    base_query = _date_filter(from_arg, until_arg)

    root = _base_skeleton(verb_attrs if not resumption_token else {"verb": verb})
    container = etree.SubElement(root, _qn(verb))

    remaining = page_size
    emitted = 0
    next_state: Optional[Dict[str, Any]] = None

    while coll_index < len(colls) and remaining > 0:
        coll_name = colls[coll_index]
        acronym = _acronym_of(coll_name)
        coll = db[coll_name]

        query = dict(base_query)
        if last_id is not None:
            query["_id"] = {"$gt": last_id}

        docs = list(coll.find(query).sort("_id", 1).limit(remaining + 1))
        has_extra = len(docs) > remaining
        page_docs = docs[:remaining]

        for doc in page_docs:
            if verb == "ListRecords":
                _append_record(container, doc, acronym)
            else:  # ListIdentifiers: <header> elements go straight in the container
                rec = _extract_record(doc) or {"header": {"identifier": doc.get("_id")}}
                _append_header(container, rec)
            emitted += 1
            served += 1

        if page_docs:
            last_id = page_docs[-1]["_id"]

        if has_extra:
            # more documents remain in this same collection
            remaining = 0
            next_state = {"coll_index": coll_index, "last_id": last_id}
        else:
            remaining -= len(page_docs)
            coll_index += 1
            last_id = None

    if next_state is None and coll_index < len(colls):
        # page filled exactly at a collection boundary; resume at next collection
        next_state = {"coll_index": coll_index, "last_id": None}

    if emitted == 0:
        return _error("noRecordsMatch", "No records match the request", verb_attrs)

    if next_state is not None:
        next_state["served"] = served
        next_state["prefix"] = metadata_prefix or METADATA_PREFIX
        if set_spec:
            next_state["set"] = set_spec
        if from_arg:
            next_state["from"] = from_arg
        if until_arg:
            next_state["until"] = until_arg
        rt = etree.SubElement(container, _qn("resumptionToken"))
        rt.text = _encode_token(next_state)
        rt.set("cursor", str(served - emitted))

    return _serialize(root)


def get_record(args: Dict[str, Any]):
    verb_attrs = {"verb": "GetRecord"}
    identifier = args.get("identifier")
    metadata_prefix = args.get("metadataPrefix")
    if identifier:
        verb_attrs["identifier"] = identifier
    if metadata_prefix:
        verb_attrs["metadataPrefix"] = metadata_prefix

    if not identifier:
        return _error("badArgument", "Missing required argument 'identifier'", verb_attrs)

    prefix_err = _check_prefix(metadata_prefix, verb_attrs)
    if prefix_err is not None:
        return prefix_err

    db = get_lareferencia_db()
    doc = None
    found_acronym = None
    for coll_name in _records_collections(db):
        hit = db[coll_name].find_one({"_id": identifier})
        if hit:
            doc = hit
            found_acronym = _acronym_of(coll_name)
            break

    if not doc:
        return _error("idDoesNotExist", "No record exists for this identifier", verb_attrs)

    root = _base_skeleton(verb_attrs)
    container = etree.SubElement(root, _qn("GetRecord"))
    _append_record(container, doc, found_acronym)
    return _serialize(root)


def handle_lareferencia(args: Dict[str, Any], base_url: Optional[str] = None) -> bytes:
    """Dispatch an OAI-PMH request for the LaReferencia repository."""
    global CURRENT_REQUEST_URL
    if base_url:
        CURRENT_REQUEST_URL = base_url

    verb = args.get("verb")
    if verb == "Identify":
        return identify()
    if verb == "ListMetadataFormats":
        return list_metadata_formats()
    if verb == "ListSets":
        return list_sets()
    if verb == "ListRecords":
        return _paginate("ListRecords", args)
    if verb == "ListIdentifiers":
        return _paginate("ListIdentifiers", args)
    if verb == "GetRecord":
        return get_record(args)
    return _error("badVerb", "Illegal or missing OAI-PMH verb", {"verb": verb} if verb else None)


def stats() -> Dict[str, int]:
    """Per-institution record counts (used by the /lareferencia/stats endpoint)."""
    db = get_lareferencia_db()
    out: Dict[str, int] = {}
    total = 0
    for coll_name in _records_collections(db):
        n = int(db[coll_name].estimated_document_count())
        out[_acronym_of(coll_name)] = n
        total += n
    out["total"] = total
    return out
