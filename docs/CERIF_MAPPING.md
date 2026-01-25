# CERIF mapping plan for `works` collection

## Objetivo
Documentar la interpretación de CERIF aplicada a la colección `works`, mostrar breves notas de la especificación CERIF, detallar qué campos ya emite `src/cerif.py`, y proponer un mapeo concreto (por tipos de producto: artículo, libro, capítulo, tesis, etc.) para implementar en el servidor OAI.

## Resumen CERIF (relevante)
- Modelo basado en entidades: `Person`, `OrganizationUnit`, `Project`, `ResultPublication`/`ResultPatent`, `Event`, `Facility`, `Class`/`Classification`.
- Relaciones como entidades: las asociaciones (persona→obra, obra→proyecto) se modelan explícitamente con rol, fechas, peso.
- Componentes reutilizables: `Titles`, `Dates` (con tipo), `Identifiers` (con scheme), `Classifications` (clases y esquemas), `Names` (para organizaciones/personas), `Addresses/Contacts`.
- Multilenguaje y tipos de título/rol/estado son importantes.

## Qué hace hoy `src/cerif.py`
- Emite un `cfEntity` por documento con elementos:
  - `cfEntityId`, `cfEntityType`
  - `cfTitle` (con `lang`, `source`)
  - `cfAbstract` (reconstruye texto cuando está en índice invertido)
  - `cfIdentifier` (id + source)
  - `cfDate` (value + source)
  - `cfContributors` / `cfContributor` (nested, con `cfAffiliations` anidadas)
  - `cfSubjects` (lista libre)
  - `cfExternalURLs`
  - `cfRawJson`

Limitación principal: las personas y organizaciones se anidan dentro del `cfEntity` en vez de publicarse como entidades independientes y enlazarse mediante relaciones CERIF.

## Observaciones desde ejemplos de `works`
- Campos recurrentes: `_id`, `titles`, `abstracts`, `authors` (array con `id`, `full_name`, `affiliations`), `external_ids` (DOI, openalex, mag), `external_urls`, `date_published`/`year_published`, `bibliographic_info` (volume, issue, pages), `types` (fuente/etiqueta p.ej. article, book, thesis), `subjects` (listas con esquema fuente), `source` (journal/publisher), `author_count`, `open_access`.
- Tipos variados en `types`: `article`, `journal-article`, `book-chapter`, `book`, `thesis`, `patent` (investigar `types` existentes y normalizar a CERIF `result-types`).

## Propuesta de mapeo (campo → CERIF)

- `_id` → `cfEntity/cfEntityId`
- `collection` (works) → `cfEntity/cfEntityType` (usaremos `result-publication` o un subtype según `types`)
- `titles[]` → `cfTitle(title, lang, source, titleType)`
  - regla: si `bibliographic_info` indica `book_title` u `in_book`, mapear `titleType=chapter` o `part`
- `abstracts[]` → `cfAbstract(lang, source)`
- `external_ids[]` → `cfIdentifier(id, scheme, source)`
  - detectar DOI/ORCID/OpenAlex/MAG por URL o patrones y normalizar `scheme`
- `date_published` / `updated[]` → `cfDate(value, type, source)`
  - `type` sugerido: `published`, `accepted`, `submitted`, `updated`
- `authors[]` → generar relaciones:
  - si `person` existe en DB: emitir `cfEntity` para la persona (`cfEntityType=Person`) y emitir `cfRelation` (obra→persona) con `role` (author/editor), orden (`ranking`) y fechas si disponibles.
  - si no existe `person` como entidad, mantener `cfContributors/cfContributor` pero preferir relaciones cuando sea posible.
- `authors[].affiliations` → para cada `affiliation` emitir/normalizar `OrganizationUnit` (`cfEntityType=OrganizationUnit`) y añadir relación persona→org (`cfRelation`), además relación obra→org cuando corresponda.
- `subjects` → mapear a `cfClass` con `classScheme` = source, `classCode` = id (si existe), `label` = name.
- `bibliographic_info` → campos estructurados en `cfEntity` (publisher, volume, issue, pages, isbn, issn, publisherName) y si `book`/`chapter` incluir `cfRelation` hacia `cfEntity` tipo `Book` o `BookChapter`.
- `open_access`/`external_urls` → `cfExternalURLs` y `cfRights`/`cfOpenAccess` (estado)

## Manejo por tipo de producto (works.types)
- Article / journal-article:
  - `cfEntityType`: `result-publication` (subtype=journal-article)
  - identifiers: DOI/URL/ISSN
  - add `cfDate(type=published)` and `cfResultPublication`-like fields: journal (source.name), volume, issue, pages
- Book:
  - `cfEntityType`: `result-publication` (subtype=book)
  - add publisher, ISBN, publication_place
  - chapters: if a `work` references `in_book` or `bibliographic_info.book_title`, emit relation `isPartOf` → Book entity
- Book chapter:
  - `cfEntityType`: `result-publication` (subtype=book-chapter)
  - emit relation `isPartOf` to parent book + `chapterNumber`
- Thesis / Dissertation:
  - `cfEntityType`: `result-publication` (subtype=thesis)
  - map degree, institution (affiliation), date

## Implementación incremental recomendada
1. Normalizar `cfIdentifier` (emitir `scheme` y `source`) and `cfDate(type)` — cambio pequeño, alto impacto.
2. Emitir `cfClass` para `subjects` en lugar de texto plano.
3. Emitir `cfEntity` separados para `person` y `affiliations` cuando existan en la DB y añadir `cfRelation` entre `works` y `person` (author role).
4. Añadir mapeo específico por `types` (book/chapter/thesis) usando `bibliographic_info` y `types`.

## Ejemplo de XML objetivo (simplificado)
```
<cfEntity>
  <cfEntityId>68ade9918c9a28c93c2696ac</cfEntityId>
  <cfEntityType>result-publication</cfEntityType>
  <cfTitle><title lang="en">...</title><titleType>main</titleType></cfTitle>
  <cfIdentifier><id>https://doi.org/...</id><scheme>doi</scheme><source>crossref</source></cfIdentifier>
  <cfDate><value>1973-01-01</value><type>published</type></cfDate>
  <cfClass><code>Geology</code><classScheme>openalex</classScheme></cfClass>
  <cfRelation><from>person:XYZ</from><to>result-publication:68ade...</to><role>Author</role><order>1</order></cfRelation>
</cfEntity>
```

## Siguientes pasos (pide uno)
- A: Implemento los pasos 1–2 ahora (identifiers, dates, cfClass) y añado tests.
- B: Hago el inventario completo automático de la colección `works` (frecuencia de campos por documento) y luego implemento relaciones.
- C: Genero un PR con helpers (`_emit_cfClass`, `_emit_cfEntity_person`, `_emit_relation`) y ejemplos de salida para revisión.

---
_Generado a partir del código en `src/cerif.py` y muestras reales de la colección `works`._
