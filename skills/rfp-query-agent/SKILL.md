---
name: rfp-query-agent
description: >
  Answer questions about ingested RFP documents using the GraphRAG knowledge
  store. Automatically classifies queries as local (specific entity/document),
  global (cross-corpus trends), or hybrid, then returns a cited answer with
  source document, page number, and section.

  ALWAYS use this skill when the user asks any question about RFP content:
  "what are Halcyon's lenders", "which RFPs mention IFRS 15", "compare ESG
  requirements", "what deliverables does Meridian require", "tell me about
  community 3", or any natural-language question about the ingested documents.
---

# Skill: RFP Query Agent

## What this skill does

The primary user-facing interface for the GraphRAG knowledge store. Given a natural-language question, it:
1. Runs `query_graph.py` to retrieve relevant entities, relationships, community excerpts, and source chunks
2. You (Claude) synthesise a clear, cited answer from that structured context
3. Every factual claim is backed by a citation: document name, page number, section

**No guessing.** If the graph context does not contain enough information to answer confidently, say so and suggest how to improve coverage (e.g. add more RFPs, re-run community summarizer).

## Prerequisites

- `graph/entities.json`, `graph/relationships.json`, `graph/community_map.json` must exist
- `graph/communities/community_NN.md` files must exist (run `rfp-community-summarizer` first for best results)
- `chunks/*.json` must exist

## Step-by-step process

---

### Step 1 — Understand the question

Read the user's question. Identify:
- **Named entities** — client names, standard codes, service names, locations
- **Query intent** — specific fact lookup vs. comparison vs. trend analysis
- **Scope** — one document, one entity, or across the whole corpus

If the question is ambiguous, ask one clarifying question before proceeding.

---

### Step 2 — Run query_graph.py

```bash
python skills/rfp-query-agent/query_graph.py --query "<user question>" --type auto --top_chunks 4 --hops 1
```

Flags to adjust based on question type:

| Situation | Flags to use |
|---|---|
| Question about a single entity or document | `--type local --top_chunks 4` |
| Cross-corpus comparison ("which RFPs…", "all entities that…") | `--type global --top_chunks 2` |
| Both specific and broad | `--type hybrid --top_chunks 4 --hops 2` |
| Deep entity neighbourhood (M&A chains, regulatory chains) | `--hops 2` |

Read the full output — it contains:
- `## Matched Entities` — entities the keyword search found
- `## Relevant Relationships` — graph traversal results
- `## Relevant Communities` — community summary excerpts (for global queries)
- `## Source Chunks for Citation` — raw text from source documents with page/section refs

---

### Step 3 — Synthesise the answer

**Be crisp. No long prose. No padding.**

**For local queries (specific entity/fact):**
```
[1–2 sentence direct answer]

- Key fact 1 *(Source: filename, p.N)*
- Key fact 2 *(Source: filename, p.N)*
```

**For global queries (cross-corpus):**
```
[One-line summary finding]

- **[Doc/Entity A]:** [one line] *(p.N)*
- **[Doc/Entity B]:** [one line] *(p.N)*
```

**For hybrid queries:** Lead with the cross-corpus finding (one line), then bullet the specifics.

**Rules:**
- No introductory filler ("Based on the graph…", "Great question…")
- No concluding summaries restating what was just said
- **Prefer tables for comparisons, lists, or multi-attribute facts — they are more scannable than prose**
- Use bullet points for 2–5 discrete facts; use a table when there are 2+ columns of data
- If a question can be answered in a table or 3 bullets, do that — do not expand to prose
- Max answer length: ~150 words (excluding table content). If more detail is genuinely needed, ask the user first

---

### Step 4 — Citation format

Cite inline, at the end of the bullet or sentence. Keep it short:

- Inline: `*(filename.docx, p.3)*`
- If from a community summary: `*(Community 3)*`

If the graph context does not support the answer, say in one sentence:
> "Graph does not have enough on [topic] — add more RFPs and re-run data prep."

---

### Step 5 — Offer follow-up paths

After the answer, offer at most 2 follow-up questions as a single compact line:

> **Also try:** "What are Meridian's ESG requirements?" · "Compare lenders across all RFPs"

---

## Query examples and expected routing

| User question | Auto-detected type | Key retrieval path |
|---|---|---|
| "What are Halcyon's lenders?" | local | entity search → `has_lender` relationships → chunk citation |
| "Which RFPs mention IFRS 15?" | global | community search → communities 7 and 3 → entity list |
| "Compare ESG requirements across RFPs" | global | community 5 summary → entity list + chunk excerpts |
| "What deliverables does Meridian require?" | local | entity search → `has_deliverable` relationships |
| "What is ISQM 1?" | local | standard entity → attributes + governing relationships |
| "Which clients are PE-backed?" | global | community search → client entities with investor relationships |
| "What audit standards apply to both clients?" | hybrid | entity intersection across communities → chunk citations |

## What this skill does NOT do

- It does not load or read source PDF/DOCX files directly — it uses pre-extracted chunks only
- It does not call any external API
- It does not re-run entity extraction — that is `rfp-data-prep`'s job
- It cannot answer questions about documents not yet ingested — tell the user to add them and re-run `rfp-data-prep`
