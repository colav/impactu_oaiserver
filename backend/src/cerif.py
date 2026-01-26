from lxml import etree
from typing import Any, List

# CERIF namespace (example)
NS = "http://www.eurocris.org/ontology/cerif#"

from .mongo_client import get_db
import re

SENSITIVE_PERSON_FIELDS = ["marital_status", "birthplace", "birthdate"]
SENSITIVE_IDENTIFIER_SOURCES = [
    "cédula de ciudadanía",
    "cedula de ciudadania",
    "cédula de extranjería",
    "cedula de extranjeria",
    "passport",
    "pasaporte",
]


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

    # Remove sensitive information
    for field in SENSITIVE_PERSON_FIELDS:
        person_doc.pop(field, None)

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
        if isinstance(xid, dict):
            src = (xid.get("source") or xid.get("provenance") or "").lower()
            if src in SENSITIVE_IDENTIFIER_SOURCES:
                continue
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


def doc_to_cerif_element(doc: dict, collection: str = "entity", metadataPrefix: str = "cerif") -> etree._Element:
    db = get_db()
    # Default to CERIF 1.2 namespace
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
    if default_coar and local_name in vocab_map:
        try:
            vocab_ns = "https://www.openaire.eu/cerif-profile/vocab/" + vocab_map[local_name]
            typ = etree.SubElement(top, "{" + vocab_ns + "}Type")
            typ.text = default_coar
            # some element types require a 'scheme' attribute (e.g., Project)
            if local_name == "Project":
                try:
                    typ.set("scheme", "URI")
                except Exception:
                    pass
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
        def _abstract_to_text(t):
            if not t:
                return None
            if isinstance(t, str):
                return t
            if isinstance(t, list):
                # prefer first item if it's text-like
                return t[0] if t else None
            if isinstance(t, dict):
                # case: {'abstract': {word: [positions], ...}, 'lang': 'en', ...}
                inv = t.get("abstract")
                if isinstance(inv, dict):
                    # reconstruct by positions
                    positions = {}
                    maxpos = -1
                    for token, poslist in inv.items():
                        if not isinstance(poslist, list):
                            continue
                        for p in poslist:
                            try:
                                pi = int(p)
                            except Exception:
                                continue
                            positions[pi] = token
                            if pi > maxpos:
                                maxpos = pi
                    if maxpos >= 0:
                        arr = [None] * (maxpos + 1)
                        for idx, tok in positions.items():
                            if 0 <= idx <= maxpos:
                                arr[idx] = tok
                        return " ".join([x for x in arr if x])
                # other dict shapes: prefer common keys
                for key in ("text", "value", "abstract", "description"):
                    v = t.get(key)
                    if isinstance(v, str):
                        return v
                    if isinstance(v, list) and v:
                        return v[0]
                # fallback: join dict keys
                try:
                    return " ".join([str(k) for k in t.keys()])
                except Exception:
                    return None
            return None

        if not text:
            return
        plain = _abstract_to_text(text)
        if not plain:
            return
        el = etree.SubElement(parent, "Abstract")
        el.text = str(plain)
        # preserve language if provided
        lang = None
        if isinstance(text, dict):
            lang = text.get("lang") or text.get("language")
        el.set("{http://www.w3.org/XML/1998/namespace}lang", lang or "en")
        return el

    def _add_identifier(parent, xid):
        if not xid:
            return

        # normalize id value and detect scheme
        if isinstance(xid, dict):
            vid = xid.get("id") or xid.get("value") or xid.get("_id")
            src = xid.get("source") or xid.get("provenance")
        else:
            vid = xid
            src = None
        if vid is None:
            return
        vid = str(vid)
        scheme = (src or _detect_scheme(vid) or "other").lower()

        # map schemes to concrete CERIF element names expected by the XSD (publications)
        mapping = {
            "doi": "DOI",
            "handle": "Handle",
            "pmcid": "PMCID",
            "pmid": "PMID",
            "issn": "ISSN",
            "isbn": "ISBN",
            "url": "URL",
            "urn": "URN",
            "zdb": "ZDB-ID",
            "openalex": "URL",
            "mag": "Identifier",
        }
        tag = mapping.get(scheme)
        if tag is None:
            # fallback: pick URL if it looks like one, otherwise generic Identifier
            tag = "URL" if vid.startswith("http") else "Identifier"

        # normalize some identifier values for compliance with XSD simpleTypes
        if tag == "DOI":
            # DOI__SimpleType expects the canonical DOI (e.g. 10.1234/abcd)
            m = re.search(r"10\.[0-9]+\/.+", vid)
            if m:
                vid = m.group(0)
            else:
                # try to strip common doi URL prefixes
                vid = re.sub(r"^https?://(dx\.)?doi\.org/", "", vid, flags=re.I)

        el = etree.SubElement(parent, tag)
        el.text = vid
        # if we emitted a generic Identifier element, ensure it has the required
        # `type` attribute (cfGenericIdentifier__Type requires @type anyURI)
        if tag == "Identifier":
            type_uri = None
            # try to form a reasonable type URI from scheme or source
            if scheme in ("doi", "handle"):
                type_uri = f"https://w3id.org/cerif/vocab/IdentifierTypes#{scheme.upper()}"
            elif scheme in ("issn", "isbn"):
                type_uri = f"https://w3id.org/cerif/vocab/IdentifierTypes#{scheme.upper()}"
            elif scheme:
                slug = re.sub(r'[^a-z0-9]+', '-', scheme.lower())
                type_uri = f"https://example.org/identifier-scheme/{slug}"
            else:
                type_uri = "urn:cerif:identifier:unknown"
            el.set("type", type_uri)
        return el

    def _add_person_identifier(parent, xid):
        # identifiers allowed in PersonIdentifers__Group: ORCID, AlternativeORCID, ResearcherID, ScopusAuthorID, ISNI, DAI, Identifier, ElectronicAddress
        if not xid:
            return
        if isinstance(xid, dict):
            vid = xid.get("id") or xid.get("value") or xid.get("_id")
            src = (xid.get("source") or xid.get("provenance") or "").lower()
        else:
            vid = str(xid)
            src = ""

        if src in SENSITIVE_IDENTIFIER_SOURCES:
            return

        if not vid:
            return
        vid = str(vid)
        scheme = src or _detect_scheme(vid)
        scheme = (scheme or "").lower()
        person_map = {
            "orcid": "ORCID",
            "isni": "ISNI",
            "scopus": "ScopusAuthorID",
            "researcherid": "ResearcherID",
        }
        tag = person_map.get(scheme)
        if not tag:
            # URLs as electronic addresses
            if vid.startswith("http"):
                tag = "ElectronicAddress"
            else:
                tag = "Identifier"
        el = etree.SubElement(parent, tag)
        el.text = vid
        if tag == "Identifier":
            # ensure required @type, slugify scheme to create valid URI fragment
            s = (scheme or "unknown").lower()
            slug = re.sub(r"[^a-z0-9]+", "-", s)
            type_uri = f"https://example.org/identifier-scheme/{slug}"
            el.set("type", type_uri)
        return el

    def _add_org_identifier(parent, xid):
        # identifiers allowed in OrgUnitIdentifiers__Group: RORID, GRID, ISNI, Identifier, ElectronicAddress, FundRefID, etc.
        if not xid:
            return
        if isinstance(xid, dict):
            vid = xid.get("id") or xid.get("value") or xid.get("_id")
            src = (xid.get("source") or xid.get("provenance") or "").lower()
        else:
            vid = str(xid)
            src = ""
        if not vid:
            return
        vid = str(vid)
        scheme = src or _detect_scheme(vid)
        scheme = (scheme or "").lower()
        org_map = {
            "ror": "RORID",
            "grid": "GRID",
            "isni": "ISNI",
        }
        tag = org_map.get(scheme)
        if not tag:
            if vid.startswith("http"):
                tag = "ElectronicAddress"
            else:
                tag = "Identifier"
        el = etree.SubElement(parent, tag)
        el.text = vid
        if tag == "Identifier":
            type_uri = f"https://example.org/identifier-scheme/{scheme or "unknown"}"
            el.set("type", type_uri)
        return el

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
        # collect abstract and identifiers, but emit them after PublicationDate to match OpenAIRE ordering
        abs_ = doc.get("abstracts") or doc.get("descriptions") or doc.get("abstract")
        identifiers = list(doc.get("external_ids") or doc.get("identifiers") or [])
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
            # emit bibliographic fields that come before the publication identifiers
            bib = doc.get("bibliographic_info") or {}
            # common keys: number, volume, issue, edition, start_page, end_page
            num = doc.get("number") or bib.get("number")
            vol = doc.get("volume") or bib.get("volume")
            iss = doc.get("issue") or bib.get("issue")
            ed = doc.get("edition") or bib.get("edition")
            sp = doc.get("start_page") or bib.get("start_page") or bib.get("page_start") or None
            ep = doc.get("end_page") or bib.get("end_page") or bib.get("page_end") or None
            if num:
                _text(top, "Number", num)
            if vol:
                _text(top, "Volume", vol)
            if iss:
                _text(top, "Issue", iss)
            if ed:
                _text(top, "Edition", ed)
            if sp:
                _text(top, "StartPage", sp)
            if ep:
                _text(top, "EndPage", ep)

        for xid in identifiers:
            _add_identifier(top, xid)
        # emit abstract after PublicationDate+Identifiers to follow XSD ordering
        if isinstance(abs_, list):
            _add_abstract(top, abs_[0] if abs_ else None)
        else:
            _add_abstract(top, abs_)

    elif local_name == "Person":
        # Remove sensitive information
        for field in SENSITIVE_PERSON_FIELDS:
            doc.pop(field, None)

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
            _add_person_identifier(top, xid)

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
            _add_org_identifier(top, xid)

    return top
