---
name: rfp-community-summarizer
description: >
  Read the Louvain community clusters from the knowledge graph and write a
  plain-English markdown summary for each community. These summaries are the
  foundation for global queries — they let Claude answer cross-corpus questions
  without loading every source document.

  ALWAYS use this skill when the user says things like: "summarize communities",
  "generate community summaries", "write community files", "run the summarizer",
  or after rfp-data-prep completes and prompts the user to run this skill.
---

# Skill: RFP Community Summarizer

## What this skill does

After `rfp-data-prep` builds the graph, each community is just a cluster of entity IDs — no prose, no context. This skill fills that gap: for each community, Claude reads the member entities, their relationships, and relevant source chunks, then writes a structured markdown summary to `graph/communities/community_NN.md`.

These files serve two purposes:
- **Global queries** — `query_graph.py` reads them to answer "which RFPs…", "compare across…", "all entities that…" questions without loading source documents
- **Human review** — you can open any `community_NN.md` to understand what a cluster represents

## Prerequisites

- `graph/community_map.json` must exist (run `rfp-data-prep` first)
- `graph/entities.json` and `graph/relationships.json` must exist
- `chunks/` directory must contain chunk JSON files (produced by `rfp-data-prep`)

## Step-by-step process

---

### Step 1 — Read community map

Read `graph/community_map.json`. The structure is:
```json
{
  "communities": {
    "0": {
      "id": "0",
      "entities": [{"id": "...", "name": "...", "type": "..."}],
      "entity_types": {"client": 1, "standard": 3},
      "source_docs": ["filename.docx"],
      "internal_edges": 5
    }
  },
  "node_to_community": {"entity_id": "0"}
}
```

List the communities to the user with entity counts so they can see what will be summarized.

---

### Step 2 — For each community, generate a summary

Process communities in order (0, 1, 2, …). For each:

**2a. Gather context**

From `graph/entities.json` — read full entity details for every member (name, type, aliases, attributes, source_docs).

From `graph/relationships.json` — read all relationships where both source and target are in this community (internal edges) plus relationships that cross into other communities (cross-community edges, limited to top 10 by page number).

From `chunks/` — keyword-search chunk files using entity names as keywords; pull the top 3 most relevant chunks (those with highest keyword hit count). These provide grounding quotes.

**2b. Write the summary file**

Write to `graph/communities/community_NN.md` (zero-padded number, e.g. `community_00.md`).

Use this structure:

```markdown
# Community N — [Descriptive Theme Title]

## Theme
[2-3 sentences describing what this cluster represents — the connecting thread
between the entities, not just a list of names]

## Source RFPs
- [filename] (primary / partial)

## Key Entities
- **[Type]:** [entity names]
- **[Type]:** [entity names]
[group by type, list most important first]

## [Domain-specific section]
[Add 1-3 domain-specific sections relevant to the community theme. Examples:]
[For standards clusters: a table of standards with description and RFP relevance]
[For client clusters: financial overview, operations geography, key risks]
[For service clusters: scope breakdown, delivery requirements]
[For ESG/regulatory clusters: compliance framework breakdown]

## Cross-community Connections
[Brief note on how this community connects to other communities — e.g.
"Community 0 (Halcyon) requires services from Community 3 (Audit Services)"]

## Strategic Significance
[1-2 sentences on why this cluster matters for RFP proposal work — what
capability or knowledge area it signals]
```

**Theme title guidelines:**
- Be specific: "Halcyon Agri-Industrial — Private PE-Backed SEA Operations" not "Client Group"
- Capture the dominant pattern: "Global Audit Standards & Quality Management" not "Standards"
- If a community is a singleton (1 entity, isolated), title it "[Entity Name] (Isolated Node)" and note it will gain connections as more RFPs are added

---

### Step 3 — Update community_map.json with summary references

After writing all files, read `graph/community_map.json` and add a `"summary_file"` key to each community entry pointing to its markdown file path (relative). Write the updated JSON back.

---

### Step 4 — Report to user

```
Community summaries written.
  Communities summarized: N
  Files written: graph/communities/community_00.md … community_NN.md

These summaries power global queries. Run rfp-query-agent to start querying.
```

List any communities skipped (e.g. singletons with no source chunks) and explain why.

## Quality standards for summaries

- Every summary must have a meaningful Theme section — do not just list entity names
- Standards communities must include a comparison table (standard | scope | RFP relevance)
- Client communities must include financial highlights from entity attributes if available
- Cross-community connections must name the other community number and theme
- Summaries should be 300–600 words — long enough to be useful for retrieval, short enough to load many at once
- Do not invent facts not present in entities.json, relationships.json, or source chunks
