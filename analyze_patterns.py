"""
RFI Nexus — client-side pattern discovery (no GDS / AuraDS required).

Pulls the Consideration / CTR_Articles / MSC / Indication subgraph out of
AuraDB with plain Cypher (works on the free tier), builds it in memory
with NetworkX, and runs the same two algorithms the original pitch called
for: Louvain community detection and degree centrality.

Setup:
    pip install networkx neo4j

Usage:
    python analyze_patterns.py
"""

import os
import networkx as nx
from networkx.algorithms.community import louvain_communities
from neo4j import GraphDatabase

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

FETCH_QUERY = """
MATCH (a)-[r]-(b)
WHERE (a:RFI OR a:Consideration OR a:CTR_Articles OR a:MSC OR a:Indication)
  AND (b:RFI OR b:Consideration OR b:CTR_Articles OR b:MSC OR b:Indication)
RETURN
  elementId(a) AS a_id, labels(a)[0] AS a_label,
  coalesce(a.ctr_article_name, a.msc_country, a.indication_name, a.consideration_id, a.rfi_id) AS a_name,
  elementId(b) AS b_id, labels(b)[0] AS b_label,
  coalesce(b.ctr_article_name, b.msc_country, b.indication_name, b.consideration_id, b.rfi_id) AS b_name
"""


def fetch_graph(driver):
    graph = nx.Graph()
    with driver.session() as session:
        for record in session.run(FETCH_QUERY):
            graph.add_node(record["a_id"], label=record["a_label"], name=record["a_name"])
            graph.add_node(record["b_id"], label=record["b_label"], name=record["b_name"])
            graph.add_edge(record["a_id"], record["b_id"])
    return graph


def run_louvain(graph):
    communities = louvain_communities(graph, seed=42)
    print(f"\nFound {len(communities)} communities:\n")
    for i, community in enumerate(communities):
        members = [f'{graph.nodes[n]["label"]}: {graph.nodes[n]["name"]}' for n in community]
        print(f"  Community {i} ({len(members)} nodes):")
        for m in members:
            print(f"    - {m}")


def run_degree_centrality(graph, top_n=10):
    centrality = nx.degree_centrality(graph)
    ranked = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top_n]
    print(f"\nTop {top_n} hub nodes by degree centrality:\n")
    for node_id, score in ranked:
        n = graph.nodes[node_id]
        print(f"  {n['label']}: {n['name']}  —  {score:.3f}")


if __name__ == "__main__":
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        g = fetch_graph(driver)
        print(f"Loaded graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
        if g.number_of_nodes() == 0:
            print("No data found — make sure you've loaded RFI data into AuraDB first.")
        else:
            run_louvain(g)
            run_degree_centrality(g)
    finally:
        driver.close()