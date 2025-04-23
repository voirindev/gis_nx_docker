# import the necessary libraries
from flask import Flask, jsonify, request

import os
import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString
import logging
from logging.handlers import RotatingFileHandler
import json
from shapely.geometry import Point
from scipy.spatial import cKDTree
import numpy as np
import pyproj
from pyproj import Proj, transform

app = Flask(__name__)

# Configuration du logging
logger = logging.getLogger('flask_app')
logger.setLevel(logging.DEBUG)

# Formatter pour les messages de log
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Handler pour la console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Handler pour le fichier (avec rotation pour limiter la taille)
file_handler = RotatingFileHandler('/app/logs/app.log', maxBytes=1000000, backupCount=5)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# the address file for the redis
qc_addresses_file = os.environ.get('DATA_ADDRESS')
# the streets file for neo4j
qc_streets_file = os.environ.get('DATA_STREETS')

# init the graph of networkx
G = nx.Graph()

# all addresses
list_addresses = []

# read the shapefile using geopandas
streets_shp = gpd.read_file(qc_streets_file)

# Initialize some example data on startup
def init_addresses():
    data_qc_address = gpd.read_file(qc_addresses_file)

    logger.debug('Initializing Redis data with addresses')
    for index, rows in data_qc_address.iterrows():
        address = rows['ADRESSE']
        geometry = rows['geometry']
        coords = geometry.coords

        list_addresses.append([address, coords[0][0], coords[0][1]])
    logger.debug(f'Initialized addresses: {len(list_addresses)}')

# function to initialize the network
# all roads are in the network (they are bidirectional)
def init_network():
    
    # loop over the rows of the GeoDataFrame
    for idx, row in streets_shp.iterrows():
        geom = row.geometry
        if isinstance(geom, LineString):
            coords = list(geom.coords)
            start = coords[0]
            end = coords[-1]
            # Add the start and end points to the graph
            G.add_edge(start, end, weight=geom.length, objectid=row['OBJECTID'], speed=row['VITESSE'])
            

    # display the size of the graph
    logger.debug(f'Initialized network: {len(G.nodes)} nodes and {len(G.edges)} edges')
   
# check if the address file exists
if len(list_addresses) == 0:
    init_addresses()
# check if the network exists
if len(G.nodes) == 0:
    init_network()   

# function to search for addresses in Redis
def addressSearch(query):
    
    suggestions = []
    
    # filter the addresses (list_addresses) that start with the query
    # and add them to the matches list
    for name, lon, lat in list_addresses:
        if name.startswith(query):
            # if the name is not in the suggestions list
            # add it to the suggestions list
            if not any(suggestion['display_name'] == name for suggestion in suggestions):
                suggestions.append({"display_name": name, "lat": lat, "lon": lon})

    return suggestions

# function to search for nodes in Neo4j
def nodeSearch(latitude, longitude):
    
    locations = []
    # get the coordinates of the nodes
    nodes = list(G.nodes)
    nodes_array = np.array(nodes)  # Liste des coordonnées (x, y)

    # build the cKDTree
    tree = cKDTree(nodes_array)

    # get the coordinates of the point in the request
    # reproject the coordinates (latitude, longitude) from epsg:4326 to EPSG:32187
    # with pyproj
    transformer = pyproj.Transformer.from_crs(4326, 32187, always_xy=True)
    
    x, y = transformer.transform(float(longitude), float(latitude))
    
    point = Point(x, y)

    # find the nearest node
    distance, index = tree.query([point.x, point.y])
    nearest_node = nodes[index]
    

    locations.append({"node": nearest_node, "distance": distance})
    
    return locations


# Define the Flask routes
# home route
@app.route('/', methods=['GET'])
def home():
    return {"status": "healthy"}, 200

# route to get the address suggestions
@app.route("/suggest")
def suggest():
    query = request.args.get("q", "").lower()
    if not query or len(query) < 2:
        return jsonify([])

    search_results = addressSearch(query)

    suggestions = [
        {"label": addr['display_name']}
        for addr in search_results
        if query in addr['display_name'].lower()
    ][:10] 

    return jsonify(suggestions)

# route to get the location of the address
@app.route("/location")
def location():
    query = request.args.get("q", "")
    if not query or len(query) < 2:
        return jsonify([])

    # call the addressSearch function
    suggestions = addressSearch(query)

    return jsonify(suggestions)

# route to get the node 
@app.route("/findnode")
def findnode():
    latitude = request.args.get("lat", "")
    longitude = request.args.get("lon", "")
    if not latitude or not longitude:
        return jsonify([])
    # call the nodeSearch function
    locations = nodeSearch(latitude, longitude)

    return jsonify(locations)

# route to get the path between two addresses
@app.route("/findpath")
def findpath():
    # get the start and end addresses from the request
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    if not start or not end :
        return jsonify([])
    # find the closest address to the start and end addresses
    suggest_start = addressSearch(start)
    suggest_end = addressSearch(end)
    
    # we will use the first address found
    if len(suggest_start) > 0:
        first = suggest_start[0]
        # find the closest node to the address    
        suggest_node_start = nodeSearch(first['lat'], first['lon'])
    
    # we will use the first address found
    if len(suggest_end) > 0:
        first = suggest_end[0]
        # find the closest node to the address
        suggest_node_end = nodeSearch(first['lat'], first['lon'])
    
    # we will use the first node found
    if len(suggest_node_start) > 0:
        first_node = suggest_node_start[0]
    # we will use the first node found
    if len(suggest_node_end) > 0:
        second_node = suggest_node_end[0]

        
    logger.debug(f"first_node: {first_node} ")
    logger.debug(f"second_node: {second_node} ")

    
    # find the path between the two nodes
    path = nx.shortest_path(G, source=first_node['node'], target=second_node['node'], weight='weight')

    # display the path
    print("shortest path :", path)

    objectids = []
    for u, v in zip(path[:-1], path[1:]):
        edge_data = G.get_edge_data(u, v)
        if edge_data is not None:
            objectids.append(edge_data['objectid'])

    # reproject from epsg:32187 to EPSG:4326
    streets_shp.to_crs(epsg=4326, inplace=True)

    data_path = streets_shp[streets_shp['OBJECTID'].isin(objectids)] 
    geojson_obj = json.loads(data_path.to_json())
    
    
    # 
    length = nx.shortest_path_length(G, source=first_node['node'], target=second_node['node'], weight='weight')
    print("Total length :", length)
    
    return jsonify({"objectids": objectids, "geojson": geojson_obj, "totalCost": length, "nodeNames": path})



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)