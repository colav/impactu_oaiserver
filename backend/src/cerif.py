from lxml import etree
from typing import Any, List

# CERIF namespace (example)
NS = "http://www.eurocris.org/ontology/cerif#"

from .mongo_client import get_db
import re

# Fields stripped from every person document before serialisation.
# Must cover all direct PII fields present in the collection.
SENSITIVE_PERSON_FIELDS = [
    "marital_status",
    "birthplace",
    "birthdate",
    "ranking",       # internal scoring — not public
]

# Identifier source names that carry government-issued / personal IDs.
# Comparison is done case-insensitively, so listing the canonical form is enough.
SENSITIVE_IDENTIFIER_SOURCES = {
    "cédula de ciudadanía",
    "cedula de ciudadania",
    "cédula de extranjería",
    "cedula de extranjeria",
    "passport",
    "pasaporte",
    "scienti",   # scienti IDs encode the national document number
}


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
            if src.lower() in SENSITIVE_IDENTIFIER_SOURCES:
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
    # CERIF 1.2 namespace (validator uses https://www.openaire.eu/cerif-profile/1.2/)
    openaire_ns = "https://www.openaire.eu/cerif-profile/1.2/"
    coll_map = {
        "works": "Publication",
        "patents": "Patent",
        "events": "Event",
        "projects": "Project",
        "person": "Person",
        "affiliations": "OrgUnit",
        "sources": "Product",     # CERIF 1.2: Journal is not a top-level entity; use Product
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
        # Project and Event use cerif-base-namespace Type (emitted inside their own blocks)
        "Equipment": "COAR_Equipment_Types",
        "Funding": "COAR_Funding_Types",
    }
    # Add a vocab-namespace Type element with a COAR URI default.
    # Project and Event are excluded here: Project emits Type in base cerif ns inside its block;
    # Event has no mandatory Type.
    coar_defaults = {
        "Publication": "http://purl.org/coar/resource_type/c_0040",
        "Product": "http://purl.org/coar/resource_type/ACF7-8YT9",
        "Patent": "http://purl.org/coar/resource_type/c_15cd",
        "Equipment": "http://purl.org/coar/resource_type/c_18gh",
        "Funding": "http://purl.org/coar/resource_type/c_18cf",
    }
    default_coar = coar_defaults.get(local_name)
    if default_coar and local_name in vocab_map:
        try:
            vocab_ns = "https://www.openaire.eu/cerif-profile/vocab/" + vocab_map[local_name]
            typ = etree.SubElement(top, "{" + vocab_ns + "}Type")
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

    def _add_identifier(parent, xid, valid_tags=None):
        """Emit an XSD-typed identifier element.

        valid_tags: if given, only emit if the resolved tag is in this set.
        Each entity has its own allowed identifier elements per the OpenAIRE CERIF 1.2 XSD.
        """
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
        # Serialize compound (dict) IDs (e.g. {"COD_RH": "0001769468"})
        if isinstance(vid, dict):
            pairs = [f"{k}:{v}" for k, v in vid.items()]
            vid = "|".join(pairs)
        vid = str(vid)
        scheme = (src or _detect_scheme(vid) or "other").lower()

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
            tag = "URL" if vid.startswith("http") else "Identifier"

        if valid_tags is not None and tag not in valid_tags:
            return None

        if tag == "DOI":
            m = re.search(r"10\.[0-9]+\/.+", vid)
            if m:
                vid = m.group(0)
            else:
                vid = re.sub(r"^https?://(dx\.)?doi\.org/", "", vid, flags=re.I)

        el = etree.SubElement(parent, tag)
        el.text = vid
        if tag == "Identifier":
            slug = re.sub(r'[^a-z0-9]+', '-', (scheme or 'unknown').lower())
            el.set("type", f"https://example.org/identifier-scheme/{slug}")
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

        if src.lower() in SENSITIVE_IDENTIFIER_SOURCES:
            return

        if not vid:
            return
        # Serialize compound (dict) IDs (e.g. {"COD_RH": "0001769468"})
        if isinstance(vid, dict):
            pairs = [f"{k}:{v}" for k, v in vid.items()]
            vid = "|".join(pairs)
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
        # ScopusAuthorID must match pattern [0-9]{10,11}
        if tag == "ScopusAuthorID":
            m = re.search(r'(\d{10,11})', vid)
            if m:
                vid = m.group(1)
            else:
                tag = "Identifier"  # fallback if no numeric ID found
        el = etree.SubElement(parent, tag)
        el.text = vid
        if tag == "Identifier":
            # ensure required @type, slugify scheme to create valid URI fragment
            s = (scheme or "unknown").lower()
            slug = re.sub(r"[^a-z0-9]+", "-", s)
            type_uri = f"https://example.org/identifier-scheme/{slug}"
            el.set("type", type_uri)
        return el

    def _emit_person_identifiers_ordered(parent, external_ids):
        """Emit person identifiers in strict XSD order on a parent element.

        XSD: ORCID? → AlternativeORCID* → ResearcherID? → Alt* →
             ScopusAuthorID? → Alt* → ISNI? → Alt* → DAI? → Alt* →
             Identifier* → ElectronicAddress*
        """
        buckets = {
            "orcid": [], "researcherid": [], "scopus": [], "isni": [],
            "dai": [], "other": [], "url": [],
        }
        for xid in external_ids or []:
            if isinstance(xid, dict):
                src_p = (xid.get("source") or "").lower()
                vid_p = str(xid.get("id") or "")
            else:
                src_p = ""
                vid_p = str(xid)
            if src_p in SENSITIVE_IDENTIFIER_SOURCES:
                continue
            if not vid_p:
                continue
            if isinstance(vid_p, dict):
                vid_p = "|".join(f"{k}:{v}" for k, v in vid_p.items())
                vid_p = str(vid_p)
            if src_p == "orcid":
                # Normalize and validate ORCID format
                _oid = re.sub(r'^https?://orcid\.org/', '', vid_p).strip()
                _oid = _oid.replace('-', '')
                if re.match(r'^\d{15}[\dX]$', _oid):
                    # Reformat with hyphens: XXXX-XXXX-XXXX-XXXX
                    _oid = f"{_oid[0:4]}-{_oid[4:8]}-{_oid[8:12]}-{_oid[12:16]}"
                    buckets["orcid"].append(f"https://orcid.org/{_oid}")
                # Skip invalid ORCIDs silently
            elif src_p == "researcherid":
                buckets["researcherid"].append(vid_p)
            elif src_p == "scopus":
                m = re.search(r'(\d{10,11})', vid_p)
                if m:
                    buckets["scopus"].append(m.group(1))
            elif src_p == "isni":
                buckets["isni"].append(vid_p)
            elif src_p == "dai":
                buckets["dai"].append(vid_p)
            elif vid_p.startswith("http"):
                buckets["url"].append(vid_p)
            else:
                buckets["other"].append((vid_p, src_p))

        _ORDER = [
            ("orcid", "ORCID", "AlternativeORCID"),
            ("researcherid", "ResearcherID", "AlternativeResearcherID"),
            ("scopus", "ScopusAuthorID", "AlternativeScopusAuthorID"),
            ("isni", "ISNI", "AlternativeISNI"),
            ("dai", "DAI", "AlternativeDAI"),
        ]
        for bucket_key, primary_tag, alt_tag in _ORDER:
            vals = list(dict.fromkeys(buckets[bucket_key]))
            for i, v in enumerate(vals):
                tag = primary_tag if i == 0 else alt_tag
                etree.SubElement(parent, tag).text = v
        for vid_p, src_p in buckets["other"]:
            el = etree.SubElement(parent, "Identifier")
            el.text = vid_p
            slug = re.sub(r"[^a-z0-9]+", "-", (src_p or "unknown").lower())
            el.set("type", f"https://example.org/identifier-scheme/{slug}")
        for vid_p in buckets["url"]:
            etree.SubElement(parent, "ElectronicAddress").text = vid_p

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
            type_uri = f"https://example.org/identifier-scheme/{scheme or 'unknown'}"
            el.set("type", type_uri)
        return el

    if local_name == "Publication":
        import datetime as _dt

        # --- 1. Refine COAR type based on actual types in the document ---
        _coar_type_map = {
            "article": "http://purl.org/coar/resource_type/c_6501",
            "journal-article": "http://purl.org/coar/resource_type/c_6501",
            "journal article": "http://purl.org/coar/resource_type/c_6501",
            "book": "http://purl.org/coar/resource_type/c_2f33",
            "book-chapter": "http://purl.org/coar/resource_type/c_3248",
            "book chapter": "http://purl.org/coar/resource_type/c_3248",
            "conference paper": "http://purl.org/coar/resource_type/c_5794",
            "conference-paper": "http://purl.org/coar/resource_type/c_5794",
            "proceedings article": "http://purl.org/coar/resource_type/c_5794",
            "thesis": "http://purl.org/coar/resource_type/c_46ec",
            "dissertation": "http://purl.org/coar/resource_type/c_46ec",
            "report": "http://purl.org/coar/resource_type/c_93fc",
            "preprint": "http://purl.org/coar/resource_type/c_816b",
            "review": "http://purl.org/coar/resource_type/c_efa0",
            "editorial": "http://purl.org/coar/resource_type/c_b239",
            "letter": "http://purl.org/coar/resource_type/c_0857",
        }
        _vocab_pub_ns = "https://www.openaire.eu/cerif-profile/vocab/COAR_Publication_Types"
        for _dt_entry in doc.get("types") or []:
            _t_val = (_dt_entry.get("type") or "").lower() if isinstance(_dt_entry, dict) else str(_dt_entry).lower()
            if _t_val in _coar_type_map:
                _type_el = top.find("{" + _vocab_pub_ns + "}Type")
                if _type_el is not None:
                    _type_el.text = _coar_type_map[_t_val]
                break

        # --- 2. Language (XSD: Language? between Type and Title) ---
        for _lang_code in doc.get("languages") or []:
            if _lang_code:
                etree.SubElement(top, "Language").text = str(_lang_code).upper()[:2]
        # If no explicit languages field, infer from first title lang
        if not doc.get("languages"):
            for _t in (doc.get("titles") or []):
                if isinstance(_t, dict) and _t.get("lang"):
                    etree.SubElement(top, "Language").text = str(_t["lang"]).upper()[:2]
                    break

        # --- 3. Titles — preserve lang from titles array ---
        titles = doc.get("titles") or doc.get("names") or []
        if isinstance(titles, dict):
            titles = [titles]
        if titles:
            for t in titles:
                if isinstance(t, dict):
                    title_val = t.get("title") or t.get("name")
                    lang = t.get("lang") or "en"
                    if title_val:
                        t_el = etree.SubElement(top, "Title")
                        t_el.text = str(title_val)
                        t_el.set("{http://www.w3.org/XML/1998/namespace}lang", lang)
                elif t:
                    t_el = etree.SubElement(top, "Title")
                    t_el.text = str(t)
                    t_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        else:
            t = doc.get("title") or doc.get("name")
            _add_title(top, t)

        # --- 3b. PublishedIn (XSD: after Subtitle, before PublicationDate) ---
        # XSD: PublishedIn wraps a *Publication* reference (journal-as-Publication)
        # Use bare id-reference only (no child elements) to avoid XSD ordering issues
        source = doc.get("source") or {}
        if isinstance(source, dict) and source.get("id"):
            pi_el = etree.SubElement(top, "PublishedIn")
            pub_ref = etree.SubElement(pi_el, "Publication")
            pub_ref.set("id", str(source["id"]))

        # --- 3c. Abstract (collected; emitted after Authors/Keywords) ---
        abs_ = doc.get("abstracts") or doc.get("descriptions") or doc.get("abstract")

        # --- 4. Identifiers: collected from top-level doi, external_ids, and source ISSN ---
        identifiers = []
        top_doi = doc.get("doi")
        if top_doi:
            identifiers.append({"source": "doi", "id": top_doi})
        for xid in doc.get("external_ids") or doc.get("identifiers") or []:
            if isinstance(xid, dict) and (xid.get("source") or "").lower() == "doi" and top_doi:
                continue  # already included via top-level doi field
            identifiers.append(xid)
        # Add ISSN/ISBN from source journal if available
        source = doc.get("source") or {}
        if isinstance(source, dict) and source.get("id"):
            # PublishedIn reference (journal) — also collect ISSNs from the source doc
            _source_doc = db["sources"].find_one({"_id": source["id"]}, {"external_ids": 1}) if "sources" in db.list_collection_names() else None
            if _source_doc:
                for xid in _source_doc.get("external_ids") or []:
                    if isinstance(xid, dict):
                        s = (xid.get("source") or "").lower()
                        if s in ("issn", "eissn", "pissn"):
                            identifiers.append({"source": "issn", "id": xid.get("id")})

        # --- 5. Publication date: date_published (unix ts) → year_published → year → updated ---
        pubdate = None
        if doc.get("date_published"):
            try:
                pubdate = _dt.datetime.utcfromtimestamp(int(doc["date_published"])).strftime("%Y-%m-%d")
            except Exception:
                pubdate = str(doc["date_published"])
        elif doc.get("publication_date"):
            try:
                pubdate = _dt.datetime.utcfromtimestamp(int(doc["publication_date"])).strftime("%Y-%m-%d")
            except Exception:
                pubdate = str(doc["publication_date"])
        elif doc.get("year_published"):
            pubdate = str(doc["year_published"])
        elif doc.get("year"):
            pubdate = str(doc["year"])
        elif doc.get("updated"):
            if isinstance(doc.get("updated"), list) and doc.get("updated"):
                _raw_t = doc["updated"][-1].get("time")
                if _raw_t:
                    try:
                        pubdate = _dt.datetime.utcfromtimestamp(int(_raw_t)).strftime("%Y-%m-%d")
                    except Exception:
                        pubdate = str(_raw_t)
        if pubdate:
            pd = etree.SubElement(top, "PublicationDate")
            pd.text = str(pubdate)

        # --- 7. Bibliographic fields ---
        bib = doc.get("bibliographic_info") or {}
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

        # --- 8. Identifiers (PublicationIdentifiers__Group: AFTER EndPage, BEFORE Authors per XSD) ---
        # XSD STRICT order: DOI?, Handle?, PMCID?, ISI-Number?, SCP-Number?, ISSN*, ISBN*, URL?, URN?, ZDB-ID?
        # Collect identifiers by type into ordered buckets then emit in correct order.
        _PUB_ID_ORDER = ["DOI", "Handle", "PMCID", "ISI-Number", "SCP-Number", "ISSN", "ISBN", "URL", "URN", "ZDB-ID"]
        _pub_id_buckets = {tag: [] for tag in _PUB_ID_ORDER}
        _pub_id_buckets["Identifier"] = []  # fallback
        # Flatten list-valued identifiers before processing
        _flat_ids = []
        for xid in identifiers:
            if not xid:
                continue
            if isinstance(xid, dict):
                vid = xid.get("id") or xid.get("value") or xid.get("_id")
                src = xid.get("source") or xid.get("provenance")
                if isinstance(vid, list):
                    for v in vid:
                        if v:
                            _flat_ids.append({"id": v, "source": src})
                else:
                    _flat_ids.append(xid)
            else:
                _flat_ids.append(xid)
        for xid in _flat_ids:
            if isinstance(xid, dict):
                vid = xid.get("id") or xid.get("value") or xid.get("_id")
                src = xid.get("source") or xid.get("provenance")
            else:
                vid = xid
                src = None
            if vid is None:
                continue
            if isinstance(vid, dict):
                vid = "|".join(f"{k}:{v}" for k, v in vid.items())
            vid = str(vid)
            scheme = (src or _detect_scheme(vid) or "other").lower()
            mapping = {
                "doi": "DOI", "handle": "Handle", "pmcid": "PMCID", "pmid": "PMCID",
                "issn": "ISSN", "eissn": "ISSN", "pissn": "ISSN",
                "isbn": "ISBN", "url": "URL", "urn": "URN", "zdb": "ZDB-ID",
                "openalex": "URL", "mag": "Identifier",
            }
            tag = mapping.get(scheme)
            if tag is None:
                tag = "URL" if vid.startswith("http") else "Identifier"
            if tag == "DOI":
                m = re.search(r"10\.[0-9]+\/.+", vid)
                if m:
                    vid = m.group(0)
                else:
                    vid = re.sub(r"^https?://(dx\.)?doi\.org/", "", vid, flags=re.I)
            # Split comma-separated ISBN/ISSN values into individual entries
            if tag in ("ISBN", "ISSN") and "," in vid:
                for part in vid.split(","):
                    part = part.strip()
                    if part and tag in _pub_id_buckets:
                        _pub_id_buckets[tag].append(part)
            elif tag in _pub_id_buckets:
                _pub_id_buckets[tag].append(vid)
            # Identifier fallback not in XSD order list — skip
        # Emit in strict XSD order
        # ISSN and ISBN allow multiple (maxOccurs=unbounded); all others are max 1
        _PUB_ID_MULTI = {"ISSN", "ISBN"}
        for tag in _PUB_ID_ORDER:
            vals = list(dict.fromkeys(_pub_id_buckets[tag]))  # deduplicate preserving order
            if tag not in _PUB_ID_MULTI:
                vals = vals[:1]  # max 1 for singleton elements
            for vid in vals:
                el = etree.SubElement(top, tag)
                el.text = vid

        # --- 9. Authors (XSD: Authors after identifiers, before Keywords/Abstract) ---
        authors = doc.get("authors") or []
        _person_coll_exists = "person" in db.list_collection_names()
        if authors:
            authors_el = etree.SubElement(top, "Authors")
            for _rank, author in enumerate(authors, start=1):
                author_el = etree.SubElement(authors_el, "Author")
                # 'rank' attribute is NOT allowed on Author per XSD

                person_id = author.get("id")
                person_doc = None
                if person_id and _person_coll_exists:
                    person_doc = db["person"].find_one({"_id": person_id})

                if person_doc:
                    person_el = etree.SubElement(author_el, "Person")
                    person_el.set("id", str(person_doc.get("_id", "")))
                    pn_el = etree.SubElement(person_el, "PersonName")
                    _family = person_doc.get("last_names") or person_doc.get("last_name") or []
                    _first_n = person_doc.get("first_names") or person_doc.get("first_name") or []
                    fn_el = etree.SubElement(pn_el, "FamilyNames")
                    fn_el.text = " ".join(str(x) for x in (_family if isinstance(_family, list) else [_family]) if x)
                    ff_el = etree.SubElement(pn_el, "FirstNames")
                    ff_el.text = " ".join(str(x) for x in (_first_n if isinstance(_first_n, list) else [_first_n]) if x)
                    _emit_person_identifiers_ordered(person_el, person_doc.get("external_ids"))
                elif person_id:
                    # Person not found in DB but we have an ID — emit minimal reference
                    person_el = etree.SubElement(author_el, "Person")
                    person_el.set("id", str(person_id))
                    if author.get("full_name"):
                        pn_el = etree.SubElement(person_el, "PersonName")
                        _name_parts = str(author["full_name"]).rsplit(" ", 1)
                        fn_el = etree.SubElement(pn_el, "FamilyNames")
                        fn_el.text = _name_parts[-1] if len(_name_parts) > 1 else _name_parts[0]
                        ff_el = etree.SubElement(pn_el, "FirstNames")
                        ff_el.text = _name_parts[0] if len(_name_parts) > 1 else ""
                elif author.get("full_name"):
                    # No person ID at all — emit Person from full_name so Affiliation is valid
                    person_el = etree.SubElement(author_el, "Person")
                    pn_el = etree.SubElement(person_el, "PersonName")
                    _name_parts = str(author["full_name"]).rsplit(" ", 1)
                    fn_el = etree.SubElement(pn_el, "FamilyNames")
                    fn_el.text = _name_parts[-1] if len(_name_parts) > 1 else _name_parts[0]
                    ff_el = etree.SubElement(pn_el, "FirstNames")
                    ff_el.text = _name_parts[0] if len(_name_parts) > 1 else ""

                # Author XSD: Person → Affiliation(*). DisplayName is NOT allowed.
                # Only emit Affiliations if a Person element was already created
                _has_person = author_el.find("{https://www.openaire.eu/cerif-profile/1.2/}Person") is not None

                if _has_person:
                    for aff in author.get("affiliations") or []:
                        aff_id = aff.get("id")
                        aff_el = etree.SubElement(author_el, "Affiliation")
                        org_el = etree.SubElement(aff_el, "OrgUnit")
                        if aff_id:
                            org_el.set("id", str(aff_id))
                        # OrgUnit in Author/Affiliation context is a reference — no Name child

        # --- 9b. Publishers (AFTER Authors/Editors, BEFORE License per XSD) ---
        _pub_source = doc.get("source") or {}
        if isinstance(_pub_source, dict):
            _publisher = _pub_source.get("publisher") or {}
            if isinstance(_publisher, dict) and _publisher.get("name"):
                pubs_el = etree.SubElement(top, "Publishers")
                pub_el = etree.SubElement(pubs_el, "Publisher")
                _dn = etree.SubElement(pub_el, "DisplayName")
                _dn.text = str(_publisher["name"])
                _pub_ou = etree.SubElement(pub_el, "OrgUnit")
                _pub_ou_name = etree.SubElement(_pub_ou, "Name")
                _pub_ou_name.text = str(_publisher["name"])
                _pub_ou_name.set("{http://www.w3.org/XML/1998/namespace}lang", "en")

        # --- 9c. License (AFTER Publishers, BEFORE Subject per XSD) ---
        # From source licenses
        _src_licenses = (_pub_source.get("licenses") if isinstance(_pub_source, dict) else None) or []
        for _lic in _src_licenses:
            if isinstance(_lic, dict) and _lic.get("url"):
                _lic_el = etree.SubElement(top, "License")
                _lic_el.text = str(_lic["url"])
                _lic_el.set("scheme", "https://spdx.org/licenses/")
                break  # one license is enough

        # --- 10. Keyword (AFTER License, BEFORE Abstract in XSD) ---
        # NOTE: Subject element requires URI values (cfGenericURIClassification__Type).
        # Our subject data is free text, so we emit as Keywords instead.
        _kw_seen = set()
        _ptop = doc.get("primary_topic") or {}
        if isinstance(_ptop, dict):
            for _key in ("display_name", "subfield", "field", "domain"):
                _ptval = _ptop.get(_key)
                if isinstance(_ptval, dict):
                    _ptval = _ptval.get("display_name") or _ptval.get("name")
                if _ptval and str(_ptval) not in _kw_seen:
                    kw_el = etree.SubElement(top, "Keyword")
                    kw_el.text = str(_ptval)
                    kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                    _kw_seen.add(str(_ptval))
        for subj in doc.get("subjects") or []:
            if isinstance(subj, dict):
                subj_list = subj.get("subjects") or []
                for s in subj_list:
                    if isinstance(s, dict) and s.get("name") and str(s["name"]) not in _kw_seen:
                        kw_el = etree.SubElement(top, "Keyword")
                        kw_el.text = str(s["name"])
                        kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                        _kw_seen.add(str(s["name"]))
            elif isinstance(subj, str) and subj and subj not in _kw_seen:
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(subj)
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                _kw_seen.add(subj)

        # --- 10b. Keywords from explicit keywords field ---
        for kw in doc.get("keywords") or []:
            if kw and str(kw) not in _kw_seen:
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(kw)
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                _kw_seen.add(str(kw))
        # Also emit topic display names as Keywords
        for _tp in doc.get("topics") or []:
            if isinstance(_tp, dict) and _tp.get("display_name") and str(_tp["display_name"]) not in _kw_seen:
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(_tp["display_name"])
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                _kw_seen.add(str(_tp["display_name"]))

        # --- 11. Abstract (AFTER Keywords in XSD) ---
        if isinstance(abs_, list):
            _add_abstract(top, abs_[0] if abs_ else None)
        else:
            _add_abstract(top, abs_)

        # --- 12. OriginatesFrom (project/group linkages) ---
        for grp in doc.get("groups") or []:
            if isinstance(grp, dict) and grp.get("id"):
                of_el = etree.SubElement(top, "OriginatesFrom")
                proj_el = etree.SubElement(of_el, "Project")
                proj_el.set("id", str(grp["id"]))

        # --- 13. Access rights (COAR vocabulary) ---
        oa = doc.get("open_access")
        if isinstance(oa, dict):
            _coar_access_ns = "http://purl.org/coar/access_right"
            if oa.get("is_open_access"):
                _ac_el = etree.SubElement(top, "{" + _coar_access_ns + "}Access")
                _ac_el.text = "http://purl.org/coar/access_right/c_abf2"
            else:
                _ac_el = etree.SubElement(top, "{" + _coar_access_ns + "}Access")
                _ac_el.text = "http://purl.org/coar/access_right/c_16ec"

        # --- 14. FileLocations (open access fulltext URL) ---
        _oa_url = (doc.get("open_access") or {}).get("url") if isinstance(doc.get("open_access"), dict) else None
        if not _oa_url:
            for _eu in doc.get("external_urls") or []:
                if isinstance(_eu, dict) and (_eu.get("source") or "").lower() == "open_access":
                    _oa_url = _eu.get("url")
                    break
        if _oa_url and str(_oa_url).startswith("http"):
            _fl = etree.SubElement(top, "FileLocations")
            _me = etree.SubElement(_fl, "Medium")
            _text(_me, "URI", str(_oa_url))
            _text(_me, "MimeType", "application/pdf")

    elif local_name == "Person":
        import datetime as _dt

        def _try_ts(v):
            if not v:
                return None
            try:
                return _dt.datetime.utcfromtimestamp(int(v)).strftime("%Y-%m-%d")
            except Exception:
                return str(v)

        for field in SENSITIVE_PERSON_FIELDS:
            doc.pop(field, None)

        # XSD sequence: PersonName → Gender → identifiers (ORCID…) → Affiliation
        # --- PersonName ---
        pn = etree.SubElement(top, "PersonName")
        family = doc.get("last_names") or doc.get("last_name") or []
        first  = doc.get("first_names") or doc.get("first_name") or []
        fn_el = etree.SubElement(pn, "FamilyNames")
        fn_el.text = " ".join([str(x) for x in (family if isinstance(family, list) else [family]) if x])
        ff_el = etree.SubElement(pn, "FirstNames")
        ff_el.text = " ".join([str(x) for x in (first  if isinstance(first,  list) else [first])  if x])

        # --- Gender (XSD enum: 'm' | 'f' only; must come right after PersonName) ---
        _sex_raw = doc.get("sex")
        if _sex_raw:
            _sex_lower = str(_sex_raw).lower().strip()
            _gender_val = None
            if _sex_lower in ("m", "male", "hombre", "masculino", "masc"):
                _gender_val = "m"
            elif _sex_lower in ("f", "female", "mujer", "femenino", "fem"):
                _gender_val = "f"
            if _gender_val:
                _text(top, "Gender", _gender_val)

        # --- Public identifiers (PersonIdentifiers__Group)
        #     Emit in strict XSD order using shared helper ---
        _emit_person_identifiers_ordered(top, doc.get("external_ids") or doc.get("identifiers") or [])

        # --- Current affiliations ---
        # Affiliation in Person context: OrgUnit (id-ref only) — no StartDate/EndDate per XSD
        for aff in doc.get("affiliations") or []:
            if not isinstance(aff, dict):
                continue
            aff_el  = etree.SubElement(top, "Affiliation")
            org_el  = etree.SubElement(aff_el, "OrgUnit")
            aff_id  = aff.get("id")
            if aff_id:
                org_el.set("id", str(aff_id))
            # OrgUnit here is a reference — no child elements or dates allowed per XSD

    elif local_name == "OrgUnit":
        # XSD sequence: Type(*) → Acronym? → Name(+) → [OrgUnitIdentifiers] → ElectronicAddress(*) → PartOf(*)
        #               → [RORID?, AlternativeRORID*, GRID?, AlternativeGRID*, ISNI?,
        #                AlternativeISNI*, FundRefID?, AlternativeFundRefID*, Identifier*]
        # NOTE: ElectronicAddress comes BEFORE the identifier group; PartOf before identifiers too.

        # --- Type (0 or more, first in XSD sequence) ---
        # Use org type from doc; default to generic 'Organisation' if available
        _OU_TYPE_MAP = {
            "university": "http://purl.org/spar/scoro/University",
            "research institute": "http://purl.org/spar/scoro/ResearchInstitution",
            "hospital": "http://purl.org/spar/scoro/Hospital",
            "company": "http://purl.org/spar/scoro/Company",
        }
        _OU_SCHEME = "https://w3id.org/cerif/vocab/OrganisationTypes"
        for _ot in doc.get("types") or []:
            _ot_val = (_ot.get("type") if isinstance(_ot, dict) else str(_ot) if _ot else "").lower()
            if _ot_val:
                _type_uri = _OU_TYPE_MAP.get(_ot_val, f"https://w3id.org/cerif/vocab/OrganisationTypes#{_ot_val.replace(' ','_').title()}")
                _t_el = etree.SubElement(top, "Type")
                _t_el.text = _type_uri
                _t_el.set("scheme", _OU_SCHEME)
                break

        # --- Acronym (0 or 1, before Name) ---
        _acronym = doc.get("abbreviations") or doc.get("acronym") or doc.get("alias") or []
        if isinstance(_acronym, list):
            _acronym = _acronym[0] if _acronym else None
        if isinstance(_acronym, dict):
            _acronym = _acronym.get("name") or _acronym.get("value")
        if _acronym and isinstance(_acronym, str) and _acronym.strip():
            etree.SubElement(top, "Acronym").text = _acronym.strip()

        # --- Name(+) (required, 1 or more) ---
        names = doc.get("names") or []
        if isinstance(names, dict):
            names = [names]
        for n in names:
            n_el = etree.SubElement(top, "Name")
            if isinstance(n, dict):
                val  = n.get("name") or n.get("title") or ""
                lang = n.get("lang") or "en"
            else:
                val  = str(n)
                lang = "en"
            n_el.text = str(val)
            n_el.set("{http://www.w3.org/XML/1998/namespace}lang", lang)

        # --- OrgUnitIdentifiers__Group (AFTER Name, BEFORE ElectronicAddress per XSD) ---
        # XSD order: RORID?, AlternativeRORID*, GRID?, AlternativeGRID*,
        #            ISNI?, AlternativeISNI*, FundRefID?, AlternativeFundRefID*, Identifier*
        _SORT_PRIORITY = {"ror": 0, "grid": 1, "isni": 2, "fundref": 3}
        _specific_ids = []
        _generic_ids  = []
        for xid in doc.get("external_ids") or doc.get("identifiers") or []:
            if isinstance(xid, dict):
                vid2 = str(xid.get("id") or "")
                src2 = (xid.get("source") or "").lower()
            else:
                vid2 = str(xid); src2 = ""
            if src2 in _SORT_PRIORITY:
                _specific_ids.append((xid, _SORT_PRIORITY[src2]))
            elif not vid2.startswith("http"):
                _generic_ids.append(xid)
        _specific_ids.sort(key=lambda t: t[1])
        _emitted_singletons = {"ror": 0, "grid": 0, "isni": 0, "fundref": 0}
        _SINGLE_MAP = {"ror": "RORID", "grid": "GRID", "isni": "ISNI", "fundref": "FundRefID"}
        _ALT_MAP    = {"ror": "AlternativeRORID", "grid": "AlternativeGRID",
                       "isni": "AlternativeISNI", "fundref": "AlternativeFundRefID"}
        for xid, _ in _specific_ids:
            src2 = (xid.get("source") or "").lower() if isinstance(xid, dict) else ""
            vid2 = str(xid.get("id") or xid)    if isinstance(xid, dict) else str(xid)
            if src2 in _SINGLE_MAP:
                tag2 = _SINGLE_MAP[src2] if _emitted_singletons[src2] == 0 else _ALT_MAP[src2]
                _emitted_singletons[src2] += 1
                # FundRefID must match pattern https://doi.org/10.13039/\d+
                if src2 == "fundref" and not vid2.startswith("http"):
                    vid2 = f"https://doi.org/10.13039/{vid2}"
                etree.SubElement(top, tag2).text = vid2
            else:
                _add_org_identifier(top, xid)
        for xid in _generic_ids:
            _add_org_identifier(top, xid)

        # --- ElectronicAddress (anyURI, AFTER identifiers per XSD) ---
        _emitted_urls = set()
        _id_url_patterns = ("ror.org/", "grid.ac/", "isni.org/")
        for url_entry in doc.get("external_urls") or []:
            url_val = url_entry.get("url") if isinstance(url_entry, dict) else str(url_entry)
            if url_val and str(url_val).startswith("http") and url_val not in _emitted_urls:
                if not any(p in str(url_val) for p in _id_url_patterns):
                    etree.SubElement(top, "ElectronicAddress").text = str(url_val)
                    _emitted_urls.add(url_val)
        for xid in doc.get("external_ids") or doc.get("identifiers") or []:
            if isinstance(xid, dict):
                vid2 = str(xid.get("id") or "")
                src2 = (xid.get("source") or "").lower()
                if vid2.startswith("http") and src2 not in ("ror", "grid", "isni", "fundref") and vid2 not in _emitted_urls:
                    etree.SubElement(top, "ElectronicAddress").text = vid2
                    _emitted_urls.add(vid2)

        # --- PartOf (parent org reference, AFTER ElectronicAddress) ---
        _parent_id = doc.get("parent_id") or doc.get("parent")
        if _parent_id and isinstance(_parent_id, (str, int)):
            _po_el  = etree.SubElement(top, "PartOf")
            _pou_el = etree.SubElement(_po_el, "OrgUnit")
            _pou_el.set("id", str(_parent_id))

    elif local_name == "Project":
        import datetime as _dt

        def _try_ts(v):
            if not v:
                return None
            try:
                return _dt.datetime.utcfromtimestamp(int(v)).strftime("%Y-%m-%d")
            except Exception:
                return str(v) if v else None

        # XSD sequence: Type → Acronym → Title(+) → Identifier → StartDate → EndDate → Abstract → Uses
        # Note: Project Type is in the BASE cerif namespace (not vocab namespace)
        # The Type element requires a 'scheme' attribute per the XSD
        type_el = etree.SubElement(top, "Type")
        type_el.text = "http://purl.org/coar/resource_type/c_71bd"
        type_el.set("scheme", "http://purl.org/coar/resource_type/")

        # --- Titles ---
        for t in doc.get("titles") or []:
            if isinstance(t, dict):
                tv   = t.get("title") or t.get("name") or ""
                lang = t.get("lang") or "es"
            else:
                tv   = str(t)
                lang = "es"
            if tv:
                te = etree.SubElement(top, "Title")
                te.text = tv
                te.set("{http://www.w3.org/XML/1998/namespace}lang", lang)

        # --- Identifiers (generic Identifier IS valid for Project) ---
        for xid in doc.get("external_ids") or []:
            _add_identifier(top, xid)

        # --- Start / End dates ---
        start = _try_ts(doc.get("date_init")) or (str(doc["year_init"]) if doc.get("year_init") else None)
        end   = _try_ts(doc.get("date_end"))  or (str(doc["year_end"])  if doc.get("year_end")  else None)
        if start:
            _text(top, "StartDate", start)
        if end:
            _text(top, "EndDate", end)

        # --- Consortium (groups as Partner OrgUnits) ---
        _proj_groups = doc.get("groups") or []
        if _proj_groups:
            cons_el = etree.SubElement(top, "Consortium")
            for _pg in _proj_groups:
                if isinstance(_pg, dict) and _pg.get("id"):
                    _part_el = etree.SubElement(cons_el, "Partner")
                    _pou_el = etree.SubElement(_part_el, "OrgUnit")
                    _pou_el.set("id", str(_pg["id"]))
                    if _pg.get("name"):
                        _pn_el = etree.SubElement(_pou_el, "Name")
                        _pn_el.text = str(_pg["name"])
                        _pn_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- Team (authors as Members) ---
        _proj_authors = doc.get("authors") or []
        if _proj_authors:
            team_el = etree.SubElement(top, "Team")
            for _pa in _proj_authors:
                if isinstance(_pa, dict) and _pa.get("id"):
                    _mem_el = etree.SubElement(team_el, "Member")
                    _per_el = etree.SubElement(_mem_el, "Person")
                    _per_el.set("id", str(_pa["id"]))
                    if _pa.get("full_name"):
                        _pn_el = etree.SubElement(_per_el, "PersonName")
                        _dn_el = etree.SubElement(_pn_el, "FamilyNames")
                        _name_parts = str(_pa["full_name"]).rsplit(" ", 1)
                        _dn_el.text = _name_parts[-1] if len(_name_parts) > 1 else _name_parts[0]
                        _fn_el = etree.SubElement(_pn_el, "FirstNames")
                        _fn_el.text = _name_parts[0] if len(_name_parts) > 1 else ""

        # --- Keyword (from types, after Team/Funded per XSD) ---
        # NOTE: Subject requires URI; types are free text, so we use Keyword
        for _pt in doc.get("types") or []:
            if isinstance(_pt, dict) and _pt.get("type"):
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(_pt["type"])
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- Keyword (from keywords field) ---
        for kw in doc.get("keywords") or []:
            if kw:
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(kw)
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- Abstract ---
        if doc.get("abstract"):
            ab_el = etree.SubElement(top, "Abstract")
            ab_el.text = str(doc["abstract"])
            ab_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

    elif local_name == "Patent":
        import datetime as _dt

        def _try_ts(v):
            if not v:
                return None
            try:
                return _dt.datetime.utcfromtimestamp(int(v)).strftime("%Y-%m-%d")
            except Exception:
                return str(v) if v else None

        # XSD sequence: (vocab)Type → Title(+) → VersionInfo? → RegistrationDate? → ApprovalDate?
        #               → PublicationDate? → CountryCode? → Issuer(*) → PatentNumber? →
        #               Inventors? → Holders? → Abstract(*) → Subject(*) → Keyword(*) →
        #               OriginatesFrom(*) → Predecessor(*) → References(*) → FileLocations? →
        #               [PatentIdentifiers: URL?] → [Classification*, Link*]

        # --- Titles ---
        for t in doc.get("titles") or []:
            if isinstance(t, dict):
                tv   = t.get("title") or t.get("name") or ""
                lang = t.get("lang") or "es"
            else:
                tv   = str(t)
                lang = "es"
            if tv:
                te = etree.SubElement(top, "Title")
                te.text = tv
                te.set("{http://www.w3.org/XML/1998/namespace}lang", lang)

        # --- PublicationDate (was ApprovalDate — corrected to XSD name) ---
        for upd in doc.get("updated") or []:
            if isinstance(upd, dict) and upd.get("time"):
                dv = _try_ts(upd["time"])
                if dv:
                    _text(top, "PublicationDate", dv)
                    break

        # --- Patent number (xs:string?, max 1) --- emit only first non-URL id
        _patent_num_emitted = False
        for xid in doc.get("external_ids") or []:
            if not isinstance(xid, dict):
                continue
            vid = xid.get("id")
            if not vid:
                continue
            if isinstance(vid, dict):
                vid = "|".join(f"{k}:{v}" for k, v in vid.items())
            vid = str(vid)
            if not vid.startswith("http") and not _patent_num_emitted:
                _text(top, "PatentNumber", vid)
                _patent_num_emitted = True

        # --- PatentIdentifiers group: URL? (BEFORE Inventors per XSD) ---
        _patent_url_emitted = False
        for xid in doc.get("external_ids") or []:
            if isinstance(xid, dict):
                vid = str(xid.get("id") or "")
                if vid.startswith("http") and not _patent_url_emitted:
                    etree.SubElement(top, "URL").text = vid
                    _patent_url_emitted = True
        if not _patent_url_emitted:
            for url_entry in doc.get("external_urls") or []:
                url_val = url_entry.get("url") if isinstance(url_entry, dict) else str(url_entry)
                if url_val and not _patent_url_emitted:
                    etree.SubElement(top, "URL").text = str(url_val)
                    _patent_url_emitted = True

        # --- Inventors (authors) ---
        _person_coll_exists = "person" in db.list_collection_names()
        authors = doc.get("authors") or []
        if authors:
            inventors_el = etree.SubElement(top, "Inventors")
            for _rank, author in enumerate(authors, start=1):
                if not isinstance(author, dict):
                    continue
                inv_el     = etree.SubElement(inventors_el, "Inventor")
                # 'rank' attribute is NOT allowed on Inventor per XSD
                person_el  = etree.SubElement(inv_el, "Person")
                pid = author.get("id")
                if pid:
                    person_el.set("id", str(pid))
                    if _person_coll_exists:
                        pdoc = db["person"].find_one({"_id": pid}, {"external_ids": 1, "first_names": 1, "last_names": 1})
                        if pdoc:
                            pn_el = etree.SubElement(person_el, "PersonName")
                            _fl = pdoc.get("last_names") or []
                            _fn = pdoc.get("first_names") or []
                            fam_el = etree.SubElement(pn_el, "FamilyNames")
                            fam_el.text = " ".join([str(x) for x in (_fl if isinstance(_fl, list) else [_fl]) if x])
                            fir_el = etree.SubElement(pn_el, "FirstNames")
                            fir_el.text = " ".join([str(x) for x in (_fn if isinstance(_fn, list) else [_fn]) if x])
                            _emit_person_identifiers_ordered(person_el, pdoc.get("external_ids"))
                # Inventor XSD: Person → Affiliation(*). DisplayName is NOT allowed.
                for aff in author.get("affiliations") or []:
                    aff_el = etree.SubElement(inv_el, "Affiliation")
                    org_el = etree.SubElement(aff_el, "OrgUnit")
                    aff_id = aff.get("id")
                    if aff_id:
                        org_el.set("id", str(aff_id))
                    # OrgUnit in Inventor/Affiliation context is a reference — no Name child

        # --- Holders (groups as OrgUnit holders) ---
        _pat_groups = doc.get("groups") or []
        if _pat_groups:
            holders_el = etree.SubElement(top, "Holders")
            for _hg in _pat_groups:
                if isinstance(_hg, dict) and _hg.get("id"):
                    _h_el = etree.SubElement(holders_el, "Holder")
                    _ou_el = etree.SubElement(_h_el, "OrgUnit")
                    _ou_el.set("id", str(_hg["id"]))
                    if _hg.get("name"):
                        _hn_el = etree.SubElement(_ou_el, "Name")
                        _hn_el.text = str(_hg["name"])
                        _hn_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- Abstract ---
        _pat_abs = doc.get("abstract") or ""
        if _pat_abs:
            ab_el = etree.SubElement(top, "Abstract")
            ab_el.text = str(_pat_abs)
            ab_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- Keyword (from types — Subject requires URI, types are free text) ---
        for _pt in doc.get("types") or []:
            if isinstance(_pt, dict) and _pt.get("type"):
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(_pt["type"])
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- Keyword ---
        for kw in doc.get("keywords") or []:
            if kw:
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(kw)
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- OriginatesFrom (group linkages) ---
        for grp in doc.get("groups") or []:
            if isinstance(grp, dict) and grp.get("id"):
                of_el = etree.SubElement(top, "OriginatesFrom")
                proj_el = etree.SubElement(of_el, "Project")
                proj_el.set("id", str(grp["id"]))

    elif local_name == "Event":
        import datetime as _dt

        def _try_ts(v):
            if not v:
                return None
            try:
                return _dt.datetime.utcfromtimestamp(int(v)).strftime("%Y-%m-%d")
            except Exception:
                return str(v) if v else None

        # XSD sequence: Type(*) → Acronym? → Name(+) → Place? → Country? → StartDate? → EndDate?
        #               → Description(*) → Subject(*) → Keyword(*) → Organizer(*) → Sponsor(*) → Partner(*)
        # NOT in XSD: Title, Identifier, ElectronicAddress, Abstract, Speakers

        # --- Type (required first; cfGenericURIClassification__Type needs scheme attr) ---
        _event_type_el = etree.SubElement(top, "Type")
        _event_type_el.text = "http://purl.org/coar/resource_type/c_f744"
        _event_type_el.set("scheme", "http://purl.org/coar/resource_type/")

        # --- Name (Event uses Name, NOT Title) ---
        for t in doc.get("titles") or []:
            if isinstance(t, dict):
                tv   = t.get("title") or t.get("name") or ""
                lang = t.get("lang") or "es"
            else:
                tv   = str(t)
                lang = "es"
            if tv:
                te = etree.SubElement(top, "Name")
                te.text = tv
                te.set("{http://www.w3.org/XML/1998/namespace}lang", lang)

        # --- Dates ---
        date_held = _try_ts(doc.get("date_held")) or (str(doc["year_held"]) if doc.get("year_held") else None)
        if date_held:
            _text(top, "StartDate", date_held)

        # --- Description (not Abstract — corrected to XSD name) ---
        if doc.get("abstract"):
            desc_el = etree.SubElement(top, "Description")
            desc_el.text = str(doc["abstract"])
            desc_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- Keyword (from types, AFTER Description per XSD — Subject requires URI) ---
        for _et in doc.get("types") or []:
            if isinstance(_et, dict) and _et.get("type"):
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(_et["type"])
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- Keyword ---
        for kw in doc.get("keywords") or []:
            if kw:
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(kw)
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

        # --- Organizer groups (corrected spelling: Organizer not Organiser) ---
        for grp in doc.get("groups") or []:
            if not isinstance(grp, dict):
                continue
            org_el = etree.SubElement(top, "Organizer")
            ou_el  = etree.SubElement(org_el, "OrgUnit")
            if grp.get("id"):
                ou_el.set("id", str(grp["id"]))
            if grp.get("name"):
                gn_el = etree.SubElement(ou_el, "Name")
                gn_el.text = str(grp["name"])
                gn_el.set("{http://www.w3.org/XML/1998/namespace}lang", "es")

    elif local_name == "Product":
        # sources/subjects collection — publishing venues / journals (CERIF 1.2: Product element)
        # XSD sequence: (vocab)Type → Language(*) → Name(+) → VersionInfo → [ProductIdentifiers: ARK?, DOI?, Handle?, URL?, URN?]
        #               → Creators? → Publishers? → License(*) → Description(*) → Subject(*) → Keyword(*)
        #               → PartOf? → OriginatesFrom(*) → GeneratedBy(*) → PresentedAt → Coverage → References
        #               → Access? → Dates? → FileLocations?

        # --- Languages FIRST (come before Name in XSD sequence) ---
        for lang in doc.get("languages") or []:
            if lang:
                _text(top, "Language", str(lang))

        # --- Name (not Title — Product uses Name) ---
        for n in doc.get("names") or []:
            n_el = etree.SubElement(top, "Name")
            if isinstance(n, dict):
                val  = n.get("name") or ""
                lang = n.get("lang") or "en"
            else:
                val  = str(n)
                lang = "en"
            n_el.text = str(val)
            n_el.set("{http://www.w3.org/XML/1998/namespace}lang", lang)

        # --- ProductIdentifiers__Group (AFTER Name/VersionInfo, BEFORE Creators per XSD) ---
        # XSD strict order: ARK? → DOI? → Handle? → URL? → URN?
        _prod_id_buckets = {"ARK": [], "DOI": [], "Handle": [], "URL": [], "URN": []}
        _PROD_ID_ORDER = ["ARK", "DOI", "Handle", "URL", "URN"]
        for xid in doc.get("external_ids") or []:
            if not xid:
                continue
            if isinstance(xid, dict):
                vid = str(xid.get("id") or "")
                src = (xid.get("source") or "").lower()
            else:
                vid = str(xid)
                src = ""
            if not vid:
                continue
            _prod_map = {"doi": "DOI", "handle": "Handle", "ark": "ARK", "urn": "URN"}
            tag = _prod_map.get(src)
            if tag is None:
                if vid.startswith("http"):
                    tag = "URL"
                else:
                    continue  # Product only allows ARK/DOI/Handle/URL/URN
            if tag == "DOI":
                m = re.search(r"10\.[0-9]+\/.+", vid)
                if m:
                    vid = m.group(0)
            if tag in _prod_id_buckets:
                _prod_id_buckets[tag].append(vid)
        # Also collect URLs from external_urls
        for url_entry in doc.get("external_urls") or []:
            url_val = url_entry.get("url") if isinstance(url_entry, dict) else str(url_entry)
            if url_val and str(url_val).startswith("http"):
                _prod_id_buckets["URL"].append(str(url_val))
        # Emit in XSD order (each element is optional, maxOccurs=1 except URN)
        for tag in _PROD_ID_ORDER:
            vals = list(dict.fromkeys(_prod_id_buckets[tag]))  # deduplicate
            if vals:
                etree.SubElement(top, tag).text = vals[0]  # max 1 per XSD

        # --- Publisher (XSD: Publishers → Publisher → DisplayName? → OrgUnit|Person) ---
        pub = doc.get("publisher")
        _pub_name = None
        if isinstance(pub, dict) and pub.get("name"):
            _pub_name = pub["name"]
        elif isinstance(pub, str) and pub:
            _pub_name = pub
        if _pub_name:
            pubs_el = etree.SubElement(top, "Publishers")
            pub_el  = etree.SubElement(pubs_el, "Publisher")
            _dn_el  = etree.SubElement(pub_el, "DisplayName")
            _dn_el.text = str(_pub_name)
            _pub_ou = etree.SubElement(pub_el, "OrgUnit")
            _pub_ou_nm = etree.SubElement(_pub_ou, "Name")
            _pub_ou_nm.text = str(_pub_name)
            _pub_ou_nm.set("{http://www.w3.org/XML/1998/namespace}lang", "en")

        # --- Licenses (License requires a 'scheme' attribute per XSD) ---
        for lic in doc.get("licenses") or []:
            if not isinstance(lic, dict):
                continue
            lic_type = lic.get("type") or lic.get("url")
            if lic_type:
                lic_el = etree.SubElement(top, "License")
                lic_el.text = str(lic_type)
                if str(lic_type).startswith("https://creativecommons.org"):
                    lic_el.set("scheme", "https://creativecommons.org/licenses/")
                else:
                    lic_el.set("scheme", "https://spdx.org/licenses/")
                break

        # --- Description (Product XSD has Description, not Abstract) ---
        for desc in doc.get("description") or []:
            if isinstance(desc, dict):
                d_text = desc.get("text") or desc.get("description") or ""
                d_lang = desc.get("lang") or "en"
            elif desc:
                d_text = str(desc)
                d_lang = "en"
            else:
                continue
            if d_text:
                d_el = etree.SubElement(top, "Description")
                d_el.text = str(d_text)
                d_el.set("{http://www.w3.org/XML/1998/namespace}lang", d_lang)

        # --- Keyword (from subjects — Subject requires URI, text goes to Keyword) ---
        for subj in doc.get("subjects") or []:
            if isinstance(subj, dict):
                subj_list = subj.get("subjects") or []
                for s in subj_list:
                    if isinstance(s, dict) and s.get("name"):
                        kw_el = etree.SubElement(top, "Keyword")
                        kw_el.text = str(s["name"])
                        kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")

        # --- Keywords ---
        for kw in doc.get("keywords") or []:
            if kw:
                kw_el = etree.SubElement(top, "Keyword")
                kw_el.text = str(kw)
                kw_el.set("{http://www.w3.org/XML/1998/namespace}lang", "en")

        # --- Open access — COAR Access Right (AFTER Keywords/PartOf/OriginatesFrom per XSD) ---
        _coar_access_ns = "http://purl.org/coar/access_right"
        if doc.get("open_access_start_year") is not None:
            ac_el = etree.SubElement(top, "{" + _coar_access_ns + "}Access")
            ac_el.text = "http://purl.org/coar/access_right/c_abf2"

    return top
