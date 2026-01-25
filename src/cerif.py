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
    """Return a cfEntity element for a person given a person reference (id or dict).

    This will fetch from `person` collection if possible. If not found, returns None.
    """
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
    # names
    names = person_doc.get("names") or person_doc.get("titles") or []
    if isinstance(names, dict):
        names = [names]
    for n in names:
        ne = etree.SubElement(cent, "cfName")
        if isinstance(n, dict):
            _text(ne, "name", n.get("name") or n.get("full_name"))
        else:
            ne.text = str(n)
    # identifiers
    for xid in person_doc.get("external_ids") or person_doc.get("identifiers") or []:
        _emit_identifier(cent, xid)
    return cent


def doc_to_cerif_element(doc: dict, collection: str = "entity") -> etree._Element:
    """Map a MongoDB document into a reasonably rich CERIF-like XML element.

    Returns a wrapper element `cfEntities` containing one or more `cfEntity` children.
    The primary entity for `doc` is the first child.
    """
    db = get_db()

    wrapper = etree.Element("cfEntities", nsmap={None: NS})

    ent = etree.SubElement(wrapper, "cfEntity")

    _text(ent, "cfEntityId", doc.get("_id") or doc.get("id"))
    _text(ent, "cfEntityType", collection)

    # Titles / names
    titles = doc.get("titles") or doc.get("names") or []
    if isinstance(titles, dict):
        titles = [titles]
    for t in titles:
        if isinstance(t, dict):
            te = etree.SubElement(ent, "cfTitle")
            _text(te, "title", t.get("title") or t.get("name"))
            if t.get("lang"):
                _text(te, "lang", t.get("lang"))
            if t.get("source"):
                _text(te, "source", t.get("source"))
        else:
            te = etree.SubElement(ent, "cfTitle")
            te.text = str(t)

    # Abstracts / descriptions
    abstracts = doc.get("abstracts") or doc.get("descriptions") or doc.get("abstract")
    if isinstance(abstracts, list):
        for a in abstracts:
            if isinstance(a, dict):
                raw = a.get("abstract") or a.get("description")
                text = None
                if isinstance(raw, dict):
                    try:
                        positions = []
                        for token, poslist in raw.items():
                            if isinstance(poslist, (list, tuple)):
                                for p in poslist:
                                    try:
                                        positions.append((int(p), str(token)))
                                    except Exception:
                                        continue
                            else:
                                try:
                                    positions.append((int(poslist), str(token)))
                                except Exception:
                                    continue
                        positions.sort(key=lambda x: x[0])
                        text = " ".join([t for _, t in positions])
                    except Exception:
                        text = None
                if text is None:
                    text = raw if isinstance(raw, str) else (a.get("description") or str(raw))
                ae = etree.SubElement(ent, "cfAbstract")
                ae.text = text
                if a.get("lang"):
                    _text(ae, "lang", a.get("lang"))
            else:
                ae = etree.SubElement(ent, "cfAbstract")
                ae.text = str(a)
    elif abstracts:
        ae = etree.SubElement(ent, "cfAbstract")
        if isinstance(abstracts, dict):
            ae.text = abstracts.get("abstract") or str(abstracts)
        else:
            ae.text = str(abstracts)

    # External identifiers
    ext_ids = doc.get("external_ids") or doc.get("identifiers") or []
    if isinstance(ext_ids, dict):
        ext_ids = [ext_ids]
    for xid in ext_ids:
        _emit_identifier(ent, xid)

    # Dates
    updated = doc.get("updated") or doc.get("dates") or []
    if isinstance(updated, dict):
        updated = [updated]
    for u in updated:
        _emit_date(ent, u)

    # Authors / persons -> try to resolve person entities and emit relations
    authors = doc.get("authors") or doc.get("creators") or []
    if isinstance(authors, dict):
        authors = [authors]
    if authors:
        contribs = etree.SubElement(ent, "cfContributors")
        order = 1
        for a in authors:
            c = etree.SubElement(contribs, "cfContributor")
            if isinstance(a, dict):
                _text(c, "name", a.get("full_name") or a.get("name"))
                if a.get("id"):
                    _text(c, "id", a.get("id"))
                # affiliations nested
                if a.get("affiliations"):
                    affs = etree.SubElement(c, "cfAffiliations")
                    for af in a.get("affiliations"):
                        af_el = etree.SubElement(affs, "cfAffiliation")
                        if isinstance(af, dict):
                            _text(af_el, "id", af.get("id"))
                            _text(af_el, "name", af.get("name"))
                        else:
                            af_el.text = str(af)
                # attempt to resolve person entity in DB and append it to wrapper
                if a.get("id"):
                    person_ent = _emit_person_entity(db, a.get("id"))
                    if person_ent is not None:
                        wrapper.append(person_ent)
                        # add a simple relation element in main entity
                        rel = etree.SubElement(ent, "cfRelation")
                        _text(rel, "from", f"person:{a.get('id')}")
                        _text(rel, "to", f"{collection}:{doc.get('_id')}")
                        _text(rel, "role", a.get("role") or "Author")
                        _text(rel, "order", order)
            else:
                c.text = str(a)
            order += 1

    # Subjects / keywords -> cfClass
    subjects = doc.get("subjects") or doc.get("keywords") or []
    if subjects:
        for s in subjects:
            # subjects may be container with source->subjects
            if isinstance(s, dict) and s.get("subjects"):
                for ss in s.get("subjects"):
                    _emit_cfClass(ent, ss)
            else:
                _emit_cfClass(ent, s)

    # External URLs
    urls = doc.get("external_urls") or doc.get("links") or []
    if isinstance(urls, dict):
        urls = [urls]
    if urls:
        links = etree.SubElement(ent, "cfExternalURLs")
        for u in urls:
            uel = etree.SubElement(links, "cfURL")
            if isinstance(u, dict):
                _text(uel, "source", u.get("source"))
                _text(uel, "url", u.get("url") or u.get("link"))
            else:
                uel.text = str(u)

    # Add a raw JSON snapshot for completeness
    try:
        import json
        raw = etree.SubElement(ent, "cfRawJson")
        raw.text = json.dumps(doc, default=str, ensure_ascii=False)
    except Exception:
        pass

    return wrapper
