---
name: rfp-data-prep
description: >
  Ingest RFP documents (PDF, DOCX, PPTX) from the rfp_data/ folder, extract
  entities and relationships using Claude's intelligence, build a knowledge
  graph with community detection, and generate an interactive HTML visualisation.

  ALWAYS use this skill when the user says things like: "prep my RFP data",
  "process my RFPs", "ingest documents", "build the knowledge graph",
  "extract entities from RFPs", "run data prep", or "I've added new RFPs".
---

# Skill: RFP Data Preparation

## What this skill does

Full ingestion pipeline for RFP documents. It:
1. Extracts plain text and chunked JSON from every PDF/DOCX/PPTX in `rfp_data/`
2. You (Claude) read each extracted text file and extract structured entities and relationships
3. Builds the NetworkX knowledge graph and runs Louvain community detection
4. Regenerates the interactive HTML knowledge graph visualisation

**No external API calls.** Python scripts handle deterministic file work; Claude handles all intelligence (entity extraction).

## Prerequisites

The user must have the project folder open in Claude Cowork (the `Smart_RAG/` folder selected as workspace).

Python dependencies must be installed:
```
pip install python-docx pymupdf python-pptx networkx python-louvain
```

## Step-by-step process

---

### Step 1 — Run text extraction (Python)

Run this bash command:
```bash
python skills/rfp-data-prep/extract_text.py
```

This reads every file in `rfp_data/` and produces:
- `extracted_text/<docname>.txt` — full plain text per document
- `chunks/<docname>_chunks.json` — 400-word chunks with page and section metadata for citation

Tell the user how many files were processed and list any errors.

---

### Step 2 — Extract entities and relationships (Claude intelligence)

For **each** `.txt` file in `extracted_text/`, read it and extract structured entities and relationships following the schema below.

**Entity schema** — write to `graph/entities.json` (array, append across all docs):

```json
{
  "id": "snake_case_unique_id",
  "name": "Human readable name",
  "type": "one of the 14 types below",
  "aliases": ["alternative names"],
  "source_docs": ["filename.docx"],
  "attributes": { "key": "value pairs relevant to the type" }
}
```

Entity types (use exactly these strings):
`client`, `service_provider`, `service`, `investor`, `standard`, `regulator`,
`location`, `concept`, `lender`, `financial_instrument`, `acquisition_target`,
`technology`, `exchange`, `deliverable`

**Relationship schema** — write to `graph/relationships.json` (array):

```json
{
  "source": "entity_id",
  "target": "entity_id",
  "relation_type": "one of the types below",
  "source_doc": "filename.docx",
  "page": 3,
  "description": "optional one-line context"
}
```

Relationship types (use exactly these strings):
`requires`, `issued_by`, `owned_by`, `governed_by`, `located_in`, `operates_in`,
`has_lender`, `acquired`, `uses`, `requires_audit_focus`, `mentions`,
`has_deliverable`, `listed_on`, `has_instrument`, `similar_to`, `part_of`,
`has_budget`

**Extraction guidelines:**
- Extract every named entity that has a meaningful relationship to something else — do not extract isolated mentions
- For standards (IFRS, ISA, IAS, SOX, ISQM, IESBA, ISSB, CSRD) always create a `standard` entity
- For locations extract country/city only if the entity operates in or is located there
- For concepts extract audit focus areas, complex accounting topics, and reporting themes
- If a document is already in `entities.json` (same `source_doc`), skip it — do not duplicate
- Use `snake_case` for all entity IDs, replace spaces and special chars with `_`
- For budget or fee references (indicative audit fee, fee budget, annual fee, total engagement cost), create a `financial_instrument` entity for the budget value and link it to the relevant service with `has_budget`
- After processing all files, write the final merged arrays to `graph/entities.json` and `graph/relationships.json`

Tell the user: total entities extracted, breakdown by type, and any documents skipped.

---

### Step 3 — Build graph and detect communities (Python)

Run:
```bash
python skills/rfp-data-prep/build_graph.py
```

This loads `entities.json` + `relationships.json`, builds the NetworkX graph, runs Louvain community detection, and writes:
- `graph/community_map.json` — full community membership map
- `graph/graph_stats.json` — node/edge/community counts

Tell the user how many communities were detected and the largest ones by entity count.

Then prompt the user:
> "Communities are ready. Run the **rfp-community-summarizer** skill next so I can write a plain-English summary for each community. These summaries power global queries later."

---

### Step 4 — Regenerate knowledge graph visualisation (Python)

Run:
```bash
python skills/rfp-data-prep/generate_graph_html.py
```

Output: `graph/knowledge_graph.html` — open in any browser to verify the graph visually.

Present the file to the user.

---

## Error handling

- If `rfp_data/` is empty: tell the user to drop PDF/DOCX/PPTX files there and re-run
- If `extract_text.py` fails on a file: log the error, skip that file, continue
- If `build_graph.py` reports zero edges: warn the user that entity extraction may have produced no relationships — check `relationships.json`
- If a community appears with only 1 node (singleton): this is normal for isolated entities; note it but do not treat it as an error

## Output summary to give the user

After completing all steps:
```
Data prep complete.
  Documents processed : N
  Entities extracted  : N  (N standards, N clients, N locations, ...)
  Relationships       : N
  Communities found   : N
  Graph visualisation : graph/knowledge_graph.html

Next step: run rfp-community-summarizer to generate community summaries.
```
