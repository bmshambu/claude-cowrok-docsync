"""
query_graph.py
--------------
Called by Claude (rfp-query-agent skill) at query time.
Searches the GraphRAG knowledge store and returns relevant context + citations.

Usage:
    python scripts/query_graph.py --query "Which RFPs mention IFRS 15?"
    python scripts/query_graph.py --query "What are Halcyon's lenders?" --type local
    python scripts/query_graph.py --query "ESG requirements across RFPs" --type global
    python scripts/query_graph.py --query "SAP" --top_chunks 5
"""

import json, argparse, re
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent.parent.parent
GRAPH_DIR     = ROOT / "graph"
CHUNKS_DIR    = ROOT / "chunks"
ENTITIES_FILE = GRAPH_DIR / "entities.json"
RELATIONS_FILE= GRAPH_DIR / "relationships.json"
COMMUNITY_FILE= GRAPH_DIR / "community_map.json"
COMMUNITIES_DIR = GRAPH_DIR / "communities"


# ── Load data ─────────────────────────────────────────────────────────────────

def load_all():
    entities      = json.loads(ENTITIES_FILE.read_text(encoding="utf-8"))
    relationships = json.loads(RELATIONS_FILE.read_text(encoding="utf-8"))
    community_map = json.loads(COMMUNITY_FILE.read_text(encoding="utf-8"))

    # Load all chunks into memory (indexed by doc_id)
    chunks_by_doc = {}
    for chunk_file in CHUNKS_DIR.glob("*_chunks.json"):
        chunks = json.loads(chunk_file.read_text(encoding="utf-8"))
        for c in chunks:
            doc_id = c["doc_id"]
            if doc_id not in chunks_by_doc:
                chunks_by_doc[doc_id] = []
            chunks_by_doc[doc_id].append(c)

    return entities, relationships, community_map, chunks_by_doc


# ── Entity search ─────────────────────────────────────────────────────────────

def search_entities(query: str, entities: list[dict], top_n: int = 10) -> list[dict]:
    """Return entities whose name/aliases/type match query keywords."""
    keywords = re.findall(r'\w+', query.lower())
    scored = []
    for e in entities:
        text = " ".join([
            e.get("name", ""),
            e.get("type", ""),
            " ".join(e.get("aliases", [])),
            json.dumps(e.get("attributes", {}))
        ]).lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:top_n]]


# ── Relationship traversal ────────────────────────────────────────────────────

def get_neighbours(entity_ids: set, relationships: list[dict], hops: int = 1) -> dict:
    """
    Return all entities reachable within `hops` from seed entity_ids.
    Returns {entity_id: [list of relationships]}
    """
    visited = set(entity_ids)
    frontier = set(entity_ids)
    result_rels = []

    for _ in range(hops):
        next_frontier = set()
        for r in relationships:
            if r["source"] in frontier or r["target"] in frontier:
                result_rels.append(r)
                next_frontier.add(r["source"])
                next_frontier.add(r["target"])
        frontier = next_frontier - visited
        visited |= next_frontier

    return {"entity_ids": list(visited), "relationships": result_rels}


# ── Chunk search ──────────────────────────────────────────────────────────────

def search_chunks(query: str, chunks_by_doc: dict,
                  filter_docs: list[str] = None, top_n: int = 5) -> list[dict]:
    """Keyword search over chunks. Optionally filter to specific doc_ids."""
    keywords = re.findall(r'\w+', query.lower())
    stop_words = {"the", "and", "for", "are", "was", "with", "that", "this",
                  "have", "from", "they", "will", "been", "what", "which", "how"}
    keywords = [k for k in keywords if k not in stop_words and len(k) > 2]

    scored = []
    for doc_id, chunks in chunks_by_doc.items():
        if filter_docs and doc_id not in filter_docs:
            continue
        for chunk in chunks:
            text = chunk["text"].lower()
            score = sum(text.count(kw) for kw in keywords)
            if score > 0:
                scored.append((score, chunk))

    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_n]]


# ── Community search ──────────────────────────────────────────────────────────

def search_communities(query: str, community_map: dict, top_n: int = 3) -> list[dict]:
    """Find the most relevant communities for a global query."""
    keywords = re.findall(r'\w+', query.lower())
    communities = community_map.get("communities", {})
    scored = []

    for comm_id, comm in communities.items():
        # Score against entity names + types in community
        entity_text = " ".join(
            f"{e['name']} {e['type']}" for e in comm.get("entities", [])
        ).lower()
        # Score against community summary if available
        summary_text = comm.get("summary", "").lower()

        # Try reading summary file
        summary_file = COMMUNITIES_DIR / f"community_{int(comm_id):02d}.md"
        if summary_file.exists():
            summary_text += " " + summary_file.read_text(encoding="utf-8").lower()

        full_text = entity_text + " " + summary_text
        score = sum(full_text.count(kw) for kw in keywords)
        if score > 0:
            scored.append((score, comm_id, comm))

    scored.sort(key=lambda x: -x[0])
    return [(comm_id, comm) for _, comm_id, comm in scored[:top_n]]


# ── Classify query ────────────────────────────────────────────────────────────

def classify_query(query: str, matched_entities: list[dict]) -> str:
    """
    local  → specific entity/doc referenced
    global → broad/comparative question
    hybrid → both
    """
    q = query.lower()
    global_signals  = ["all", "across", "compare", "which rfp", "common", "trend",
                       "every", "both", "overall", "summary", "list all", "how many"]
    local_signals   = ["in the", "for halcyon", "for meridian", "rfp_", "in rfp",
                       "what is", "what are", "specific", "detail"]

    has_global = any(s in q for s in global_signals)
    has_local  = any(s in q for s in local_signals) or len(matched_entities) <= 2

    if has_global and has_local:
        return "hybrid"
    if has_global:
        return "global"
    return "local"


# ── Format output ─────────────────────────────────────────────────────────────

def format_result(query: str, query_type: str,
                  matched_entities: list[dict],
                  traversal: dict,
                  top_chunks: list[dict],
                  relevant_communities: list) -> str:

    lines = []
    lines.append(f"# Query Result")
    lines.append(f"**Query:** {query}")
    lines.append(f"**Type:** {query_type.upper()}")
    lines.append("")

    # Matched entities
    if matched_entities:
        lines.append(f"## Matched Entities ({len(matched_entities)})")
        for e in matched_entities[:8]:
            docs = ", ".join(e.get("source_docs", []))
            aliases = ", ".join(e.get("aliases", []))
            lines.append(f"- **{e['name']}** [{e['type']}]")
            if aliases:
                lines.append(f"  Aliases: {aliases}")
            lines.append(f"  Source: {docs}")
        lines.append("")

    # Relationships from traversal
    rels = traversal.get("relationships", [])
    if rels:
        lines.append(f"## Relevant Relationships ({len(rels)})")
        seen = set()
        for r in rels[:15]:
            key = f"{r['source']}→{r['target']}"
            if key not in seen:
                seen.add(key)
                lines.append(
                    f"- {r['source']} **{r['relation_type']}** {r['target']}"
                    f"  *(Source: {r.get('source_doc','?')}, Page {r.get('page','?')})*"
                )
        lines.append("")

    # Community summaries (global)
    if relevant_communities:
        lines.append(f"## Relevant Communities ({len(relevant_communities)})")
        for comm_id, comm in relevant_communities:
            summary_file = COMMUNITIES_DIR / f"community_{int(comm_id):02d}.md"
            lines.append(f"### Community {comm_id}")
            lines.append(f"Entities: {len(comm['entities'])} | Docs: {', '.join(comm['source_docs'])}")
            top_entities = ", ".join(e['name'] for e in comm['entities'][:4])
            lines.append(f"Key entities: {top_entities}")
            if summary_file.exists():
                # Include first 600 chars of summary
                summary = summary_file.read_text(encoding="utf-8")
                first_block = summary[:800].strip()
                lines.append(f"\n*Summary excerpt:*\n{first_block}...")
            lines.append("")

    # Source chunks
    if top_chunks:
        lines.append(f"## Source Chunks for Citation ({len(top_chunks)})")
        for c in top_chunks:
            lines.append(
                f"### [{c['chunk_id']}]"
                f"  📄 {c['filename']} | Page {c['page_start']}–{c['page_end']} | Section: {c['section']}"
            )
            lines.append(f"> {c['text'][:500]}...")
            lines.append("")
            lines.append(
                f"**Citation:** *Source: {c['filename']}, "
                f"Page {c['page_start']}, Section: \"{c['section']}\"*"
            )
            lines.append("")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Query the RFP GraphRAG knowledge store")
    parser.add_argument("--query",      required=True, help="User question")
    parser.add_argument("--type",       default="auto",
                        choices=["auto", "local", "global", "hybrid"],
                        help="Query type override (default: auto-detect)")
    parser.add_argument("--top_chunks", type=int, default=4,
                        help="Number of source chunks to return (default: 4)")
    parser.add_argument("--hops",       type=int, default=1,
                        help="Graph traversal hops from matched entities (default: 1)")
    args = parser.parse_args()

    entities, relationships, community_map, chunks_by_doc = load_all()

    # 1. Find matching entities
    matched_entities = search_entities(args.query, entities)

    # 2. Classify query
    query_type = args.type if args.type != "auto" else classify_query(args.query, matched_entities)

    # 3. Graph traversal (local + hybrid)
    traversal = {"entity_ids": [], "relationships": []}
    if query_type in ("local", "hybrid") and matched_entities:
        seed_ids = {e["id"] for e in matched_entities[:5]}
        traversal = get_neighbours(seed_ids, relationships, hops=args.hops)

    # 4. Community search (global + hybrid)
    relevant_communities = []
    if query_type in ("global", "hybrid"):
        relevant_communities = search_communities(args.query, community_map, top_n=3)

    # 5. Chunk search — filter to docs from matched entities if local
    filter_docs = None
    if query_type == "local" and matched_entities:
        filter_docs = list({
            doc for e in matched_entities[:5]
            for doc in e.get("source_docs", [])
        })
        # Convert filenames to doc_ids
        filter_docs = [
            Path(d).stem.replace(" ", "_") for d in filter_docs
        ]

    top_chunks = search_chunks(args.query, chunks_by_doc,
                               filter_docs=filter_docs,
                               top_n=args.top_chunks)

    # 6. Format and print
    result = format_result(
        query=args.query,
        query_type=query_type,
        matched_entities=matched_entities,
        traversal=traversal,
        top_chunks=top_chunks,
        relevant_communities=relevant_communities
    )
    print(result)


if __name__ == "__main__":
    main()
