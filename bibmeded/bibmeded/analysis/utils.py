import networkx as nx

def graph_to_d3(G: nx.Graph) -> dict:
    nodes = [{"id": n, **G.nodes[n]} for n in G.nodes()]
    links = [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)]
    return {"nodes": nodes, "links": links}
