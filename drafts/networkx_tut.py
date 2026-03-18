import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

# undirected graph
G = nx.Graph()
G.add_edge('A', 'B', weight=1)
G.add_edge('A', 'C', weight=4)
G.add_edge('B', 'D', weight=2)
G.add_edge('C', 'D', weight=1)
G.add_edge('C', 'E', weight=3)
G.add_edge('D', 'E', weight=2)
# G.add_node('F')

# edge_list=[(1,2),(1,3),(2,4),(3,4),(3,5),(4,5)]
# G.add_edges_from(edge_list)

print(nx.shortest_path(G, source='A', target='E'))

#nx.draw(G, with_labels=True)
nx.draw_planar(G, with_labels=True)

plt.show()
# check if is connected
if(nx.is_connected(G)):
    print("The graph is connected.")
else:
    print("The graph is not connected.")


# directed graph
DG = nx.DiGraph()

# MultiGraph , multiple edges between the same nodes
MG = nx.MultiGraph()

# MultiDiGraph , multiple directed edges between the same nodes
MDG = nx.MultiDiGraph()


# G = nx.from_numpy_array(np.array([
#     [0, 1, 0],
#     [1, 1, 1],
#     [0, 0, 0]
# ]))


# nx.draw(G, with_labels=True)
# plt.show()

# nx.draw_shell(G, with_labels=True)
# plt.show()

# nx.draw_circular(G, with_labels=True)
# plt.show()

# nx.draw_spectral(G, with_labels=True)
# plt.show()

# #nx.draw_random(G, with_labels=True)
# #plt.show()

# #nx.draw_planar(G, with_labels=True)
# plt.show()


# check node degree 

for node in G.nodes():
    degree = G.degree(node)
    print(f"Node {node} has degree {degree}.")


print("node [A] degree: ", G.degree('A'))
print("node [B] degree with Dict: ", dict(G.degree)['B'])

# what is Centrality in graph theory?
# Centrality is a measure of the importance or influence of a node within a graph. 
# It quantifies how central a node is in the network, which can be based on various 
# criteria such as the number of connections (degree centrality), the shortest paths 
# that pass through the node (betweenness centrality), or the closeness to all other 
# nodes (closeness centrality). Centrality measures help identify key nodes that may 
# play crucial roles in the structure and function of the network. 

# Degree Centrality
degree_centrality = nx.degree_centrality(G)
print("Degree Centrality:", degree_centrality)
# Betweenness Centrality
betweenness_centrality = nx.betweenness_centrality(G)
print("Betweenness Centrality:", betweenness_centrality)
# Closeness Centrality
closeness_centrality = nx.closeness_centrality(G)
print("Closeness Centrality:", closeness_centrality)
# Eigenvector Centrality
eigenvector_centrality = nx.eigenvector_centrality(G)
print("Eigenvector Centrality:", eigenvector_centrality)
# PageRank
pagerank = nx.pagerank(G)
print("PageRank:", pagerank)

# check completeness of the graph
# if nx.is_complete(G):
#     print("The graph is complete.")
# else:
#     print("The graph is not complete.")

G1 = nx.complete_graph(5)
G2 = nx.path_graph(5)


# what is Density in graph theory?
# Density is a measure of how many edges are 
# in a graph compared to the maximum possible number
# of edges. It is calculated as the ratio of the number 
# of edges to the number of possible edges in the graph.
# For an undirected graph with n nodes, the maximum number 
# of edges is n(n-1)/2, while for a directed graph, it is n(n-1).
density = nx.density(G)
print("Density of the graph:", density)

# what is Diameter in graph theory?
# Diameter is the longest shortest path between 
# any two nodes in a graph.
if nx.is_connected(G):
    diameter = nx.diameter(G)
    print("Diameter of the graph:", diameter)
else:
    print("Cannot compute diameter: Graph is not connected.")
    
# Eulerian Path and Circuit
# An Eulerian path is a path in a graph that visits every edge exactly once.
# An Eulerian circuit is an Eulerian path that starts and ends at the same vertex.
if nx.is_eulerian(G):
    print("The graph has an Eulerian circuit.")
    print("Eulerian circuit:", list(nx.eulerian_circuit(G)))
elif nx.has_eulerian_path(G):
    print("The graph has an Eulerian path.")
    print("Eulerian path:", list(nx.eulerian_path(G)))
else:
    print("The graph does not have an Eulerian path or circuit.")


# Bridge and Articulation Point
# A bridge is an edge whose removal increases the number of connected components in a graph.
# An articulation point is a vertex whose removal increases the number of connected components in a graph.
bridges = list(nx.bridges(G))
articulation_points = list(nx.articulation_points(G))
print("Bridges in the graph:", bridges)
print("Articulation points in the graph:", articulation_points)


