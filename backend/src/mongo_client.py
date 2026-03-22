import os
import logging
from pymongo import MongoClient, ASCENDING

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "kahi")

_client = None
_indexes_created = False

_logger = logging.getLogger(__name__)

# Indexes to create on startup for efficient OAI-PMH pagination and lookups.
# Each entry: (collection_name, [(field, direction), ...], optional kwargs dict)
OAI_INDEXES = [
    # works (publications)
    ("works", [("updated.time", ASCENDING)]),
    ("works", [("authors.id", ASCENDING)]),
    ("works", [("source.id", ASCENDING)]),
    ("works", [("doi", ASCENDING)]),
    # person
    ("person", [("updated.time", ASCENDING)]),
    ("person", [("external_ids.source", ASCENDING), ("external_ids.id", ASCENDING)]),
    ("person", [("affiliations.id", ASCENDING)]),
    # affiliations (OrgUnits)
    ("affiliations", [("updated.time", ASCENDING)]),
    ("affiliations", [("external_ids.source", ASCENDING), ("external_ids.id", ASCENDING)]),
    ("affiliations", [("parent_id", ASCENDING)]),
    ("affiliations", [("names.name", ASCENDING)]),
    # sources (Products/journals)
    ("sources", [("updated.time", ASCENDING)]),
    ("sources", [("external_ids.source", ASCENDING)]),
    # projects
    ("projects", [("updated.time", ASCENDING)]),
    ("projects", [("authors.id", ASCENDING)]),
    # patents
    ("patents", [("updated.time", ASCENDING)]),
    ("patents", [("authors.id", ASCENDING)]),
    # events
    ("events", [("updated.time", ASCENDING)]),
    ("events", [("authors.id", ASCENDING)]),
]


def _ensure_indexes(db):
    """Create indexes if they don't already exist. Safe to call multiple times."""
    global _indexes_created
    if _indexes_created:
        return
    existing_colls = set(db.list_collection_names())
    for coll_name, keys, *rest in OAI_INDEXES:
        if coll_name not in existing_colls:
            continue
        kwargs = rest[0] if rest else {}
        try:
            db[coll_name].create_index(keys, background=True, **kwargs)
        except Exception as e:
            _logger.warning("Index creation failed on %s %s: %s", coll_name, keys, e)
    _indexes_created = True
    _logger.info("OAI indexes ensured")


def get_db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    db = _client[DB_NAME]
    _ensure_indexes(db)
    return db


def get_collection(name: str = "entities"):
    """Return the named collection from the `kahi` database (default: `entities`)."""
    return get_db()[name]
