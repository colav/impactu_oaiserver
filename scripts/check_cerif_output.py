#!/usr/bin/env python3
"""Simple smoke test: serialize CERIF output for one `works` document.

Usage: python scripts/check_cerif_output.py
"""
import sys
import json
from lxml import etree
from src.mongo_client import get_collection
from src.cerif import doc_to_cerif_element


def main():
    c = get_collection("works")
    doc = c.find_one()
    if not doc:
        print("No document found in works collection", file=sys.stderr)
        return 2
    wrapper = doc_to_cerif_element(doc, collection="works")
    xml = etree.tostring(wrapper, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    print(xml.decode("utf-8"))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
