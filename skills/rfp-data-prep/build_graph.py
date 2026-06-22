"""
build_graph.py
--------------
Loads graph/entities.json + graph/relationships.json (written by Claude entity extraction)
→ Builds a NetworkX graph
→ Runs Louvain community detection
→ Writes graph/community_map.json

Usage:
    python scripts/build_graph.py [--resolution 1.0]
"""

import json, argparse
from pathlib import Path

import networkx as nx
import community as community_louvain  # python-louvain

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT            = Path(__file__).parent.parent.parent
GRAPH_DIR       = ROOT / "graph"
ENTITIES_FILE   = GRAPH_DIR / "entities.json"
RELATIONS_FILE  = GRAPH_DIR / "relationships.json"
COMMUNITY_FILE  = GRAPH_DIR / "community_map.json"
GRAPH_FILE      = GRAPH_DIR / "graph_stats.json"

GRAPH_DIR.mkdir(exist_ok=True)


# ── Load data ─────────────────────────────────────────────────────────────────

def load_entities() -> list[dict]:
    if not ENTITIES_FILE.exists():
        raise FileNotFoundError(
            "graph/entities.json not found.\n"
            "Run entity extraction via Claude Cowork first."
        )
    return json.loads(ENTITIES_FILE.read_text(encoding="utf-8"))


def load_relationships() -> list[dict]:
    if not RELATIONS_FILE.exists():
        raise FileNotFoundError(
            "graph/relationships.json not found.\n"
            "Run entity extraction via Claude Cowork first."
        )
    return json.loads(RELATIONS_FILE.read_text(encoding="utf-8"))


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph(entities: list[dict], relationships: list[dict]) -> nx.Graph:
    G = nx.Graph()

    # Add entity nodes
    for e in entities:
        G.add_node(
            e["id"],
            name        = e.get("name", e["id"]),
            entity_type = e.get("type", "unknown"),
            aliases     = e.get("aliases", []),
            source_docs = e.get("source_docs", [])
        )

    # Add relationship edges (weighted by frequency)
    for r in relationships:
        src = r.get("source")
        tgt = r.get("target")
        if not src or not tgt:
            continue
        if not G.has_node(src) or not G.has_node(tgt):
            continue

        if G.has_edge(src, tgt):
            G[src][tgt]["weight"] += 1
            G[src][tgt]["relations"].append(r.get("relation_type", "related"))
        else:
            G.add_edge(
                src, tgt,
                weight        = 1,
                relations     = [r.get("relation_type", "related")],
                source_doc    = r.get("source_doc", ""),
                page          = r.get("page")
            )

    print(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


# ── Community detection ───────────────────────────────────────────────────────

def detect_communities(G: nx.Graph, resolution: float) -> dict:
    """
    Returns {node_id: community_id} partition.
    Uses Louvain on the largest connected component if graph is disconnected.
    """
    if G.number_of_nodes() == 0:
        return {}

    partition = community_louvain.best_partition(G, resolution=resolution, random_state=42)
    return partition


def build_community_map(entities: list[dict], partition: dict, G: nx.Graph) -> dict:
    """
    Returns community_map: {
        "communities": {
            "0": {
                "id": 0,
                "entities": [...],
                "entity_types": {...counts...},
                "source_docs": [...],
                "internal_edges": N,
                "summary": ""   ← filled by Claude in next step
            }
        },
        "node_to_community": {node_id: community_id}
    }
    """
    entity_lookup = {e["id"]: e for e in entities}
    communities: dict[str, dict] = {}

    for node_id, comm_id in partition.items():
        comm_key = str(comm_id)
        if comm_key not in communities:
            communities[comm_key] = {
                "id"           : comm_id,
                "entities"     : [],
                "entity_types" : {},
                "source_docs"  : set(),
                "internal_edges": 0,
                "summary"      : ""   # Claude fills this in rfp-community-summarizer
            }

        entity = entity_lookup.get(node_id, {"id": node_id, "name": node_id, "type": "unknown", "source_docs": []})
        communities[comm_key]["entities"].append({
            "id"   : entity.get("id"),
            "name" : entity.get("name"),
            "type" : entity.get("type", "unknown")
        })

        etype = entity.get("type", "unknown")
        communities[comm_key]["entity_types"][etype] = \
            communities[comm_key]["entity_types"].get(etype, 0) + 1

        for doc in entity.get("source_docs", []):
            communities[comm_key]["source_docs"].add(doc)

    # Count internal edges per community
    for u, v in G.edges():
        if partition.get(u) == partition.get(v):
            comm_key = str(partition[u])
            communities[comm_key]["internal_edges"] += 1

    # Convert sets → lists for JSON serialisation
    for c in communities.values():
        c["source_docs"] = sorted(c["source_docs"])

    return {
        "communities"       : communities,
        "node_to_community" : {k: str(v) for k, v in partition.items()}
    }


# ── Stats ─────────────────────────────────────────────────────────────────────

def print_community_report(community_map: dict):
    comms = community_map["communities"]
    print(f"\n  Detected {len(comms)} communities:\n")
    for cid, c in sorted(comms.items(), key=lambda x: -len(x[1]["entities"])):
        types_str = ", ".join(f'{v}×{k}' for k, v in c["entity_types"].items())
        docs_str  = ", ".join(c["source_docs"]) or "—"
        print(f"  Community {cid:>3} │ {len(c['entities']):>3} entities │ {types_str}")
        print(f"              │ docs: {docs_str}")
        top = [e["name"] for e in c["entities"][:5]]
        print(f"              │ top : {', '.join(top)}")
        print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", type=float, default=1.0,
                        help="Louvain resolution (>1 = more communities, <1 = fewer)")
    args = parser.parse_args()

    print(f"\n🔧 Building graph  (resolution={args.resolution})\n")

    entities      = load_entities()
    relationships = load_relationships()
    print(f"  Loaded {len(entities)} entities, {len(relationships)} relationships")

    G             = build_graph(entities, relationships)
    partition     = detect_communities(G, args.resolution)
    community_map = build_community_map(entities, partition, G)

    # Save
    COMMUNITY_FILE.write_text(
        json.dumps(community_map, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Save graph stats
    stats = {
        "nodes"       : G.number_of_nodes(),
        "edges"       : G.number_of_edges(),
        "communities" : len(community_map["communities"]),
        "resolution"  : args.resolution,
        "entities"    : len(entities),
        "relationships": len(relationships)
    }
    GRAPH_FILE.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print_community_report(community_map)

    print(f"✅ community_map.json written → {COMMUNITY_FILE}")
    print(f"\nNext step: run rfp-community-summarizer skill in Claude Cowork")
    print(f"           (reads community_map.json → writes graph/communities/community_XX.md)")


if __name__ == "__main__":
    main()
