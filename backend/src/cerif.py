from lxml import etree
from typing import Any, List

# CERIF namespace (example)
NS = "http://www.eurocris.org/ontology/cerif#"

from .mongo_client import get_db
import re


def _text(el, tag: str, value: Any):
    if value is None:
        return
    child = etree.SubElement(el, tag)
    child.text = str(value)
    return child


def _list_to_el(parent, tag, items):
    if not items:
        return
    container = etree.SubElement(parent, tag)
    for it in items:
        item_el = etree.SubElement(container, tag[:-1]) if tag.endswith('s') else etree.SubElement(container, tag)
        if isinstance(it, dict):
            for k, v in it.items():
                _text(item_el, k, v)
        else:
            item_el.text = str(it)
    return container


def _detect_scheme(value: str) -> str:
    if not value:
        return ""
    v = str(value)
    if v.startswith("https://doi.org") or re.search(r"doi\.org/", v, re.I):
        return "doi"
    if v.startswith("https://openalex.org") or "openalex" in v:
        return "openalex"
    if re.match(r"^\d{7,}$", v) or "mag" in v.lower():
        return "mag"
    if v.startswith("http"):
        return "url"
    return "other"


def _emit_identifier(parent, xid):
    xid_el = etree.SubElement(parent, "cfIdentifier")
    if isinstance(xid, dict):
        idv = xid.get("id") or xid.get("value") or xid.get("_id")
        _text(xid_el, "id", idv)
        scheme = xid.get("scheme") or _detect_scheme(idv) if idv else None
        if scheme:
            _text(xid_el, "scheme", scheme)
        _text(xid_el, "source", xid.get("source") or xid.get("provenance"))
    else:
        _text(xid_el, "id", xid)
        _text(xid_el, "scheme", _detect_scheme(str(xid)))
    return xid_el


def _emit_date(parent, u: Any):
    de = etree.SubElement(parent, "cfDate")
    if isinstance(u, dict):
        _text(de, "value", u.get("time") or u.get("date") or u.get("year"))
        # try to infer type from source or keys
        if u.get("type"):
            _text(de, "type", u.get("type"))
        elif u.get("source"):
            _text(de, "source", u.get("source"))
    else:
        de.text = str(u)
    return de


def _emit_cfClass(parent, subj: Any):
    # subj may be dict with id/name/source, or simple string
    cl = etree.SubElement(parent, "cfClass")
    if isinstance(subj, dict):
        _text(cl, "code", subj.get("id") or subj.get("code") or subj.get("name"))
        _text(cl, "label", subj.get("name"))
        _text(cl, "classScheme", subj.get("source") or subj.get("provenance"))
    else:
        _text(cl, "label", subj)
    return cl


def _emit_person_entity(db, person_ref) -> etree._Element:
    pid = None
    if isinstance(person_ref, dict):
        pid = person_ref.get("id") or person_ref.get("_id")
    else:
        pid = person_ref
    if not pid:
        return None
    person_doc = db["person"].find_one({"_id": pid}) if "person" in db.list_collection_names() else None
    if not person_doc:
        return None
    cent = etree.Element("cfEntity")
    _text(cent, "cfEntityId", person_doc.get("_id") or person_doc.get("id"))
    _text(cent, "cfEntityType", "Person")
    names = person_doc.get("names") or person_doc.get("titles") or []
    if isinstance(names, dict):
        names = [names]
    for n in names:
        ne = etree.SubElement(cent, "cfName")
        if isinstance(n, dict):
            _text(ne, "name", n.get("name") or n.get("full_name"))
        else:
            ne.text = str(n)
    for xid in person_doc.get("external_ids") or person_doc.get("identifiers") or []:
        _emit_identifier(cent, xid)
    return cent


def _emit_org_entity(db, aff_ref) -> etree._Element:
    aid = None
    if isinstance(aff_ref, dict):
        aid = aff_ref.get("id") or aff_ref.get("_id")
    else:
        aid = aff_ref
    if not aid:
        return None
    coll_name = "affiliations"
    if coll_name not in db.list_collection_names():
        return None
    org_doc = db[coll_name].find_one({"_id": aid})
    if not org_doc:
        return None
    oent = etree.Element("cfEntity")
    _text(oent, "cfEntityId", org_doc.get("_id") or org_doc.get("id"))
    _text(oent, "cfEntityType", "OrganizationUnit")
    names = org_doc.get("names") or org_doc.get("names") or []
    if isinstance(names, dict):
        names = [names]
    for n in names:
        ne = etree.SubElement(oent, "cfName")
        if isinstance(n, dict):
            _text(ne, "name", n.get("name"))
        else:
            ne.text = str(n)
    for xid in org_doc.get("external_ids") or org_doc.get("identifiers") or []:
        _emit_identifier(oent, xid)
    if org_doc.get("country"):
        _text(oent, "cfCountry", org_doc.get("country"))
    return oent


def _normalize_result_subtype(doc: dict) -> str:
    types = doc.get("types") or []
    if isinstance(types, dict):
        types = [types]
    candidates = []
    for t in types:
        if isinstance(t, dict):
            v = t.get("type") or t.get("source")
        else:
            v = t
        if v:
            candidates.append(str(v).lower())
    bib = doc.get("bibliographic_info") or {}
    for c in candidates:
        if "thesis" in c or "dissertation" in c:
            return "thesis"
        if "book-chapter" in c or "chapter" in c:
            return "book-chapter"
        if "book" in c and "chapter" not in c:
            return "book"
        if "patent" in c:
            return "patent"
        if "article" in c or "journal" in c:
            return "article"
    if bib and (bib.get("isbn") or bib.get("publisher") or bib.get("book_title") or bib.get("in_book")):
        if bib.get("chapter") or bib.get("chapterNumber") or bib.get("in_book"):
            return "book-chapter"
        return "book"
    return "other"


def doc_to_cerif_element(doc: dict, collection: str = "entity", metadataPrefix: str = "oai_cerif_openaire_1.2") -> etree._Element:
    db = get_db()
    # Choose OpenAIRE namespace based on requested metadataPrefix
    if isinstance(metadataPrefix, str) and "1.1.1" in metadataPrefix:
        openaire_ns = "https://www.openaire.eu/cerif-profile/1.1.1/"
    else:
        openaire_ns = "https://www.openaire.eu/cerif-profile/1.2/"
    coll_map = {
        "works": "Publication",
        "patents": "Patent",
        "events": "Event",
        "projects": "Project",
        "person": "Person",
        "affiliations": "OrgUnit",
        "sources": "Product",
        "subjects": "Product",
        "equipments": "Equipment",
        "funding": "Funding",
    }
    local_name = coll_map.get(collection, "Publication")
    top = etree.Element("{" + openaire_ns + "}" + local_name, nsmap={None: openaire_ns})
    try:
        top.set("id", str(doc.get("_id")))
    except Exception:
        pass
    vocab_map = {
        "Publication": "COAR_Publication_Types",
        "Product": "COAR_Product_Types",
        "Patent": "COAR_Patent_Types",
        "Project": "COAR_Project_Types",
        "Equipment": "COAR_Equipment_Types",
        "Funding": "COAR_Funding_Types",
    }
    # Add a Type element in the OpenAIRE namespace with a COAR URI default
    coar_defaults = {
        "Publication": "http://purl.org/coar/resource_type/c_0040",
        "Product": "http://purl.org/coar/resource_type/ACF7-8YT9",
        "Patent": "http://purl.org/coar/resource_type/c_15cd",
        "Project": "http://purl.org/coar/resource_type/c_71bd",
        "Equipment": "http://purl.org/coar/resource_type/c_18gh",
        "Funding": "http://purl.org/coar/resource_type/c_18cf",
    }
    default_coar = coar_defaults.get(local_name)
    if default_coar:
        try:
            typ = etree.SubElement(top, "{" + openaire_ns + "}Type")
            typ.text = default_coar
        except Exception:
            pass

    def _add_title(parent, title_val):
        if not title_val:
            return
        el = etree.SubElement(parent, "Title")
        el.text = str(title_val)
        el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        return el

    def _add_abstract(parent, text):
        if not text:
            return
        el = etree.SubElement(parent, "Abstract")
        el.text = str(text)
        el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        return el

    def _add_identifier(parent, xid):
        if not xid:
            return
        ident = etree.SubElement(parent, "Identifier")
        if isinstance(xid, dict):
            vid = xid.get("id") or xid.get("value") or xid.get("_id")
            if vid is not None:
                ident.text = str(vid)
            src = xid.get("source") or xid.get("provenance")
            if src:
                try:
                    ident.set("type", str(src))
                except Exception:
                    pass
            else:
                scheme = _detect_scheme(vid) if vid else None
                if scheme:
                    ident.set("type", scheme)
        else:
            ident.text = str(xid)
            try:
                ident.set("type", _detect_scheme(str(xid)) or "other")
            except Exception:
                pass
        return ident

    if local_name == "Publication":
        titles = doc.get("titles") or doc.get("names") or []
        if isinstance(titles, dict):
            titles = [titles]
        if titles:
            for t in titles:
                if isinstance(t, dict):
                    _add_title(top, t.get("title") or t.get("name"))
                else:
                    _add_title(top, t)
        else:
            t = doc.get("title") or doc.get("name")
            _add_title(top, t)
        abs_ = doc.get("abstracts") or doc.get("descriptions") or doc.get("abstract")
        if isinstance(abs_, list):
            _add_abstract(top, abs_[0] if abs_ else None)
        else:
            _add_abstract(top, abs_)
        for xid in doc.get("external_ids") or doc.get("identifiers") or []:
            _add_identifier(top, xid)
        pubdate = None
        if doc.get("publication_date"):
            pubdate = doc.get("publication_date")
        elif doc.get("year"):
            pubdate = doc.get("year")
        elif doc.get("updated"):
            if isinstance(doc.get("updated"), list) and doc.get("updated"):
                pubdate = doc.get("updated")[-1].get("time")
        if pubdate:
            pd = etree.SubElement(top, "PublicationDate")
            pd.text = str(pubdate)

    elif local_name == "Person":
        pn = etree.SubElement(top, "PersonName")
        family = doc.get("last_names") or doc.get("last_name") or []
        first = doc.get("first_names") or doc.get("first_name") or []
        if isinstance(family, list):
            fn = etree.SubElement(pn, "FamilyNames")
            fn.text = " ".join([str(x) for x in family if x])
        else:
            fn = etree.SubElement(pn, "FamilyNames")
            fn.text = str(family)
        if isinstance(first, list):
            ff = etree.SubElement(pn, "FirstNames")
            ff.text = " ".join([str(x) for x in first if x])
        else:
            ff = etree.SubElement(pn, "FirstNames")
            ff.text = str(first)
        for xid in doc.get("external_ids") or doc.get("identifiers") or []:
            _add_identifier(top, xid)

    elif local_name == "OrgUnit":
        names = doc.get("names") or doc.get("name")
        if isinstance(names, list):
            n = etree.SubElement(top, "Name")
            first = names[0]
            if isinstance(first, dict):
                val = first.get("name") or first.get("title") or str(first)
            else:
                val = first
            n.text = str(val)
            n.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        elif names:
            n = etree.SubElement(top, "Name")
            n.text = str(names)
            n.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        for xid in doc.get("external_ids") or doc.get("identifiers") or []:
            _add_identifier(top, xid)

    return top
