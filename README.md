# 🧭 gis_nx_docker

**gis_nx_docker** is a ready-to-use Docker image for spatial network analysis using Python. It combines the power of `geopandas` and `networkx` to allow loading shapefiles, building graphs, computing shortest paths, and visualizing results — all in a reproducible environment.

## 🚀 Features

- Load vector data (shapefiles) with `geopandas`
- Build graphs from line geometries using `networkx`
- Compute shortest paths between nodes
- Find the nearest graph node to a given point
- Fully pre-configured Docker environment

## 🐳 Getting Started

Make sure Docker is installed on your machine. Then, run:

```bash
git clone https://github.com/voirinprof/gis_nx_docker.git
cd gis_nx_docker
docker-compose up
```

Once the container is running, open [http://localhost](http://localhost) in your browser

## 📁 Project Structure

```
gis_nx_docker/
├── docker-compose.yml
├── nginx/
│   └── nginx.conf
├── flask/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── web/
│   └── index.html
├── data/
│   └── reseau_lignes.shp

```

- `flask/`: Example of flask api
- `data/`: Directory for shapefiles and other geospatial inputs
- `web`: Example of a web page
- `docker-compose.yml`: Simplifies container setup and execution

## 📦 Main Dependencies

- Python 3.x
- geopandas
- networkx
- shapely
- scipy
- flask

## ✍️ Example Usage of networkx

A simple workflow to load a shapefile, build a graph, and compute the shortest path:

```python
import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point
from scipy.spatial import cKDTree
import matplotlib.pyplot as plt

# Load the shapefile
gdf = gpd.read_file("data/reseau_lignes.shp")

# Build the graph
G = nx.Graph()
for _, row in gdf.iterrows():
    geom = row.geometry
    if isinstance(geom, LineString):
        coords = list(geom.coords)
        for i in range(len(coords) - 1):
            start = coords[i]
            end = coords[i + 1]
            G.add_edge(start, end, weight=LineString([start, end]).length)

# Find the nearest nodes to two points
def find_nearest_node(point, nodes):
    tree = cKDTree(list(nodes))
    _, idx = tree.query((point.x, point.y))
    return list(nodes)[idx]

point_start = Point(x1, y1)
point_end = Point(x2, y2)

start_node = find_nearest_node(point_start, G.nodes)
end_node = find_nearest_node(point_end, G.nodes)

# Compute the shortest path
path = nx.shortest_path(G, source=start_node, target=end_node, weight='weight')


```

## 📚 Additional Resources

- [geopandas documentation](https://geopandas.org/)
- [networkx documentation](https://networkx.org/)
- [shapely documentation](https://shapely.readthedocs.io/)
- [scipy documentation](https://docs.scipy.org/doc/scipy/)

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

