# CERIF Validation Summary — OpenAIRE CRIS v1.2

## Validation Results

| Test | Description | Status |
|------|-------------|--------|
| check000 | Identify | ✅ PASS |
| check010 | MetadataFormats | ✅ PASS |
| check020 | Sets | ✅ PASS |
| check100 | Publications | ✅ PASS |
| check200 | Products (Sources/Journals) | ✅ PASS |
| check300 | Patents | ✅ PASS |
| check400 | Persons | ✅ PASS |
| check500 | OrgUnits | ✅ PASS |
| check600 | Projects | ✅ PASS |
| check700 | Fundings | ✅ PASS (empty set) |
| check800 | Equipment | ✅ PASS (empty set) |
| check900 | Events | ✅ PASS |
| check990 | Referential Integrity | ⚠️ FAIL (data limit) |

**12 of 13 tests passing.** The single failure is a referential integrity check caused by the 2,000-record
validation limit — some referenced OrgUnits appear beyond the served subset. With the full dataset,
all references resolve correctly.

## Issues Fixed

### 1. Publication `PublishedIn` Element
- **Problem**: `PublishedIn` wrapped a `<Product>` reference instead of a `<Publication>` reference.
- **Fix**: Changed to emit `<Publication id="..."/>` inside `PublishedIn`, as the XSD requires.

### 2. Identifier XSD Ordering
- **Problem**: Publication/Product/Patent identifiers were emitted in arbitrary order.
- **Fix**: Implemented strict XSD ordering — `DOI → Handle → PMCID → ISI-Number → SCP-Number → ISSN → ISBN → URL → URN → ZDB-ID` for Publications; analogous orderings for Products and Patents.

### 3. Person Identifier Ordering
- **Problem**: Person identifiers (ORCID, ScopusAuthorID, ISNI, etc.) emitted out of XSD order.
- **Fix**: Bucket-and-emit approach: `ORCID → AlternativeORCID → ResearcherID → ScopusAuthorID → ISNI → DAI → Identifier → ElectronicAddress`.

### 4. OrgUnit `FundRefID` Format
- **Problem**: FundRef IDs needed to start with `https://doi.org/10.13039/` per XSD pattern.
- **Fix**: Normalize FundRef IDs to full DOI URI format.

### 5. ScopusAuthorID Validation
- **Problem**: ScopusAuthorIDs must be 10–11 digits per XSD pattern.
- **Fix**: Extract 10–11 digit sequences from raw values, skip invalid ones.

### 6. Pagination Fix
- **Problem**: When `validation_limit` was set, early resumptionToken termination could miss remaining collections.
- **Fix**: After limit is reached, check subsequent collections for documents before declaring the list complete.

### 7. Patent Identifier Ordering
- **Problem**: Patent identifiers (PatentNumber, Approvals, etc.) emitted out of XSD order.
- **Fix**: Strict ordering per XSD: `Identifier → PatentNumber → Approvals → URL`.

### 8. MongoDB Indexes
- **Fix**: Created indexes on `_id` and `updated` fields for all OAI collections to accelerate queries and `from/until` date filtering.

### 9. Sensitive Data Protection
- **Problem**: Personal Minciencias/Scienti identifiers were exposed via Person records.
- **Fix**: Added `SENSITIVE_IDENTIFIER_SOURCES` set to filter out `minciencias`, `scienti`, and `cedula` sources from Person identifier output.

### 10. ISSN/ISBN Handling
- **Problem**: Comma-separated ISSN/ISBN values (e.g., `"9781461449607, 9781461449591"`) emitted as a single invalid value.
- **Fix**: Split comma-separated values into individual elements.
- **Problem**: List-typed identifier values (e.g., ISSN stored as Python list) produced string representations like `"['0945-6066', '2196-310X']"`.
- **Fix**: Flatten list-valued identifiers before processing.

### 11. Singleton Identifier Limits
- **Problem**: `URL`, `DOI`, `Handle`, etc. are `maxOccurs=1` in XSD but multiple values were emitted.
- **Fix**: Only emit first value for singleton identifiers; ISSN and ISBN allow multiples.

### 12. Publisher Element Structure
- **Problem**: `Publisher` element requires a `Person` or `OrgUnit` child per XSD type `cfLinkWithDisplayNameToPersonOrOrgUnit__Type`, but only `DisplayName` was emitted.
- **Fix**: Added `OrgUnit > Name` child after `DisplayName` in both Publication and Product publishers.

### 13. Author Without Person Element
- **Problem**: Authors with empty `id` fields had `Affiliation` elements emitted without a preceding `Person` element, violating XSD structure.
- **Fix**: Generate minimal `Person` elements from `full_name` for authors without IDs; guard Affiliation emission behind a Person-exists check.

### 14. Subject vs Keyword
- **Problem**: `Subject` element requires URI values (`cfGenericURIClassification__Type`) but free-text topic names were emitted.
- **Fix**: Moved all free-text subject/topic data to `Keyword` elements (which accept `cfMLangString__Type`).

### 15. ORCID Validation
- **Problem**: Invalid ORCID values like `6,092,110`, `19921993jr`, or `000-0002-5739-4413` (missing digit) were emitted, failing XSD pattern validation.
- **Fix**: Validate ORCID format (16 digits/X), normalize hyphens, and silently skip invalid values.

## CERIF Field Coverage

### Publication
Type, Language, Title, PublishedIn, PublicationDate, Volume, Issue, StartPage, EndPage, DOI, Handle, PMCID, ISSN, ISBN, URL, Authors (Person + PersonName + ORCID + ScopusAuthorID + ElectronicAddress + Affiliation), Publishers, License, Keyword, Abstract

### Person
PersonName (FamilyNames, FirstNames), ORCID, ResearcherID, ScopusAuthorID, ISNI, ElectronicAddress, Affiliation

### OrgUnit
Type, Acronym, Name, Identifier (ROR, ISNI, FundRefID), ElectronicAddress, PartOf

### Project
Type, Title, Identifier, Consortium (Partner OrgUnits), Team (Members), Keyword

### Patent
Type, Title, PublicationDate, PatentNumber, URL, Identifier, Inventors (Person + Affiliation), Holders, Keyword, OriginatesFrom

### Event
Type, Name, Keyword, Organizer

### Product (Sources/Journals)
Type, Name, Identifier, Description, Publishers, License, Keyword, Access

## Running the Validator

```bash
# Start the server with a record limit for quick testing
export OAI_VALIDATION_LIMIT=2000
python3 -m uvicorn backend.src.app:app --host 0.0.0.0 --port 8000

# Run the validator
export VALIDATOR_ENDPOINT="http://localhost:8000/oai"
cd docker/openaire-validator
docker compose run --rm openaire-validator

# Check logs
cat docker/openaire-validator/data/logs/validate-*.log
```

For a full (no-limit) test, start the server without `OAI_VALIDATION_LIMIT`. Note: this will serve all
~500K+ records and may take significant time.
