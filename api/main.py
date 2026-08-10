from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import mysql.connector
import math
import heapq

import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load database config from environment variables (useful for Render deployment)
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "leela")
DB_DATABASE = os.environ.get("DB_DATABASE", "waypoint_rit")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))

def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_DATABASE,
        port=DB_PORT
    )

# --- MODELS ---
class BuildingModel(BaseModel):
    name: str; total_floors: int; entrance_x: float; entrance_y: float; icon: str; color: str; footprint_coordinates: str
class RoomModel(BaseModel):
    room_id: str; building_id: int; floor_level: int; room_type: str; coordinate_x: float; coordinate_y: float; footprint_coordinates: str; branch: Optional[str] = "General"; z_coordinate: float = 3.5; color: Optional[str] = None
class MessageModel(BaseModel):
    message: str; type: str

@app.get("/")
def read_root(): return {"status": "Backend is running!"}

@app.get("/debug-db")
def debug_db():
    import traceback
    config = {
        "host": DB_HOST,
        "user": DB_USER,
        "database": DB_DATABASE,
        "port": DB_PORT,
        "password_provided": bool(DB_PASSWORD)
    }
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        return {
            "status": "Success",
            "message": "Successfully connected to the database!",
            "config": config
        }
    except Exception as e:
        return {
            "status": "Error",
            "message": str(e),
            "traceback": traceback.format_exc(),
            "config": config
        }

# --- GET ENDPOINTS (Frontend & Admin) ---
@app.get("/admin/buildings")
def get_buildings():
    try:
        conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT building_id, name, total_floors, entrance_x, entrance_y, icon, color, footprint_coordinates FROM Buildings")
        res = cursor.fetchall(); conn.close(); return res
    except Exception as e:
        print("Database fallback triggered for /admin/buildings:", e)
        return [
            {
                "building_id": 1,
                "name": "C Block - Academic",
                "total_floors": 7,
                "entrance_x": 80.0447,
                "entrance_y": 13.0390,
                "icon": "fa-building",
                "color": "#4f46e5",
                "footprint_coordinates": "[[[80.0442, 13.0379], [80.0441, 13.0382], [80.0443, 13.0396], [80.0436, 13.0398], [80.0434, 13.0404], [80.0432, 13.0411], [80.0455, 13.0413], [80.0461, 13.0409], [80.0462, 13.0392], [80.0457, 13.0376], [80.0454, 13.0373], [80.0442, 13.0379]]]"
            }
        ]

@app.get("/admin/rooms")
def get_rooms():
    try:
        conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT r.room_id, r.building_id, r.floor_level, r.room_type, r.coordinate_x, r.coordinate_y, r.footprint_coordinates, r.z_coordinate, r.color, b.name as building_name FROM Rooms r JOIN Buildings b ON r.building_id = b.building_id")
        res = cursor.fetchall(); conn.close(); return res
    except Exception as e:
        print("Database fallback triggered for /admin/rooms:", e)
        return []

@app.get("/live-data")
def get_messages():
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT status_id, message, type FROM SystemStatus ORDER BY status_id DESC")
    res = cursor.fetchall(); conn.close(); return res

@app.get("/search/{query}")
def search_location(query: str):
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT r.room_id as id, r.coordinate_x as global_x, r.coordinate_y as global_y, 'room' as type, b.name as building_name, r.building_id, r.floor_level, b.total_floors FROM Rooms r JOIN Buildings b ON r.building_id = b.building_id WHERE r.room_id LIKE %s LIMIT 1", (f"%{query}%",))
    res = cursor.fetchone()
    if not res:
        cursor.execute("SELECT building_id as id, entrance_x as global_x, entrance_y as global_y, 'building' as type, name as building_name, building_id, total_floors FROM Buildings WHERE name LIKE %s LIMIT 1", (f"%{query}%",))
        res = cursor.fetchone()
    conn.close()
    if not res: raise HTTPException(status_code=404, detail="Not found")
    return res

# --- PATHFINDING & ROUTING ENGINE ---
import json

WALKWAY_NODES = {}
WALKWAY_EDGES = {}
BUILDING_TO_NODE = {
    10: "a_entrance",
    11: "green_entrance",
    12: "b_entrance",
    13: "jobs_entrance",
    14: "c_entrance"
}
buildings_mapped = False

def load_pathways():
    global WALKWAY_NODES, WALKWAY_EDGES
    pathways_file = os.path.join(os.path.dirname(__file__), "..", "RIT Pathways.geojson")
    if not os.path.exists(pathways_file):
        pathways_file = os.path.join(os.path.dirname(__file__), "RIT Pathways.geojson")
    if not os.path.exists(pathways_file):
        pathways_file = "RIT Pathways.geojson"

    if os.path.exists(pathways_file):
        try:
            with open(pathways_file, "r") as f:
                data = json.load(f)
            
            nodes_map = {}
            nodes_coords = {}
            edges_map = {}
            
            def get_node_id(lng, lat):
                key = (round(lat, 6), round(lng, 6))
                if key not in nodes_map:
                    node_id = f"w_{len(nodes_map)}"
                    nodes_map[key] = node_id
                    nodes_coords[node_id] = key
                return nodes_map[key]
                
            for feature in data.get("features", []):
                geom = feature.get("geometry", {})
                if geom.get("type") == "LineString":
                    coords = geom.get("coordinates", [])
                    prev_node = None
                    for pt in coords:
                        node_id = get_node_id(pt[0], pt[1])
                        if prev_node and prev_node != node_id:
                            if prev_node not in edges_map:
                                edges_map[prev_node] = set()
                            if node_id not in edges_map:
                                edges_map[node_id] = set()
                            edges_map[prev_node].add(node_id)
                            edges_map[node_id].add(prev_node)
                        prev_node = node_id
            
            WALKWAY_NODES = {nid: coord for nid, coord in nodes_coords.items()}
            WALKWAY_EDGES = {nid: list(neighbors) for nid, neighbors in edges_map.items()}
            print(f"Loaded {len(WALKWAY_NODES)} pathway nodes from {pathways_file}")
        except Exception as e:
            print("Failed to load RIT Pathways.geojson:", e)
    else:
        # Static Fallback if GeoJSON not found
        WALKWAY_NODES = {
            "main_gate": (13.037528246529249, 80.04520562488239),
            "junc_south": (13.0378, 80.0451),
            "junc_center": (13.0386, 80.0450),
            "junc_north": (13.0393, 80.0449),
            "junc_ne": (13.0394, 80.0454),
            "green_entrance": (13.0380, 80.0447),
            "a_entrance": (13.0385, 80.0453),
            "b_entrance": (13.0390, 80.0450),
            "c_entrance": (13.0394, 80.0456),
            "jobs_entrance": (13.0399, 80.0447)
        }
        WALKWAY_EDGES = {
            "main_gate": ["junc_south"],
            "junc_south": ["main_gate", "green_entrance", "a_entrance", "junc_center"],
            "green_entrance": ["junc_south", "junc_center"],
            "a_entrance": ["junc_south", "junc_center"],
            "junc_center": ["green_entrance", "a_entrance", "b_entrance", "junc_north"],
            "b_entrance": ["junc_center", "junc_north"],
            "junc_north": ["b_entrance", "jobs_entrance", "junc_ne", "junc_center"],
            "jobs_entrance": ["junc_north"],
            "junc_ne": ["junc_north", "c_entrance"],
            "c_entrance": ["junc_ne"]
        }

load_pathways()

def link_buildings_to_nodes():
    global BUILDING_TO_NODE
    if any(nid.startswith("w_") for nid in WALKWAY_NODES):
        try:
            conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT building_id, entrance_x, entrance_y FROM Buildings")
            buildings = cursor.fetchall()
            conn.close()
            new_mapping = {}
            for b in buildings:
                if b["entrance_x"] and b["entrance_y"]:
                    closest = find_closest_node(b["entrance_x"], b["entrance_y"])
                    if closest:
                        new_mapping[b["building_id"]] = closest
            BUILDING_TO_NODE = new_mapping
            print(f"Mapped {len(BUILDING_TO_NODE)} buildings dynamically to GeoJSON pathways.")
        except Exception as e:
            print("Failed to map buildings to nodes dynamically:", e)

def get_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def find_closest_node(lat, lng):
    closest = None
    min_dist = float('inf')
    for node_id, coord in WALKWAY_NODES.items():
        dist = get_distance((lat, lng), coord)
        if dist < min_dist:
            min_dist = dist
            closest = node_id
    return closest

def dijkstra(start_node, end_node):
    queue = [(0.0, start_node, [])]
    visited = set()
    while queue:
        (cost, node, path) = heapq.heappop(queue)
        if node in visited:
            continue
        visited.add(node)
        
        path = path + [node]
        if node == end_node:
            return cost, path
            
        for neighbor in WALKWAY_EDGES.get(node, []):
            if neighbor not in visited:
                dist = get_distance(WALKWAY_NODES[node], WALKWAY_NODES[neighbor])
                heapq.heappush(queue, (cost + dist, neighbor, path))
    return float('inf'), []

def resolve_location(query: str):
    if "," in query:
        try:
            parts = [float(p.strip()) for p in query.split(",")]
            if len(parts) == 2:
                return {
                    "type": "coordinate",
                    "lat": parts[0],
                    "lng": parts[1],
                    "floor": 0,
                    "name": "My Location"
                }
        except:
            pass

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Search Room exact
    cursor.execute("SELECT r.room_id as id, r.coordinate_x as lat, r.coordinate_y as lng, 'room' as type, b.name as building_name, r.building_id, r.floor_level FROM Rooms r JOIN Buildings b ON r.building_id = b.building_id WHERE r.room_id = %s LIMIT 1", (query,))
    res = cursor.fetchone()
    
    if not res:
        # 2. Search Room LIKE
        cursor.execute("SELECT r.room_id as id, r.coordinate_x as lat, r.coordinate_y as lng, 'room' as type, b.name as building_name, r.building_id, r.floor_level FROM Rooms r JOIN Buildings b ON r.building_id = b.building_id WHERE r.room_id LIKE %s LIMIT 1", (f"%{query}%",))
        res = cursor.fetchone()
        
    if not res:
        # 3. Search Building exact
        cursor.execute("SELECT building_id as id, entrance_x as lat, entrance_y as lng, 'building' as type, name as building_name, building_id, 0 as floor_level FROM Buildings WHERE name = %s LIMIT 1", (query,))
        res = cursor.fetchone()
        
    if not res:
        # 4. Search Building LIKE
        cursor.execute("SELECT building_id as id, entrance_x as lat, entrance_y as lng, 'building' as type, name as building_name, building_id, 0 as floor_level FROM Buildings WHERE name LIKE %s LIMIT 1", (f"%{query}%",))
        res = cursor.fetchone()
        
    conn.close()
    
    if res:
        return {
            "type": res["type"],
            "lat": res["lat"],
            "lng": res["lng"],
            "floor": res["floor_level"],
            "building_id": res.get("building_id"),
            "name": res["id"] if res["type"] == "room" else res["building_name"]
        }
    return None

@app.get("/walkways")
def get_walkways():
    features = []
    seen_edges = set()
    for start, neighbors in WALKWAY_EDGES.items():
        for end in neighbors:
            edge_key = tuple(sorted([start, end]))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                p1 = WALKWAY_NODES[start]
                p2 = WALKWAY_NODES[end]
                features.append({
                    "type": "Feature",
                    "properties": {"type": "walkway"},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[p1[1], p1[0]], [p2[1], p2[0]]]
                    }
                })
    return {"type": "FeatureCollection", "features": features}

@app.get("/route")
def get_route(start: str, end: str):
    global buildings_mapped
    if not buildings_mapped:
        link_buildings_to_nodes()
        buildings_mapped = True
        
    start_loc = resolve_location(start)
    end_loc = resolve_location(end)
    
    if not start_loc or not end_loc:
        raise HTTPException(status_code=404, detail="Start or destination location not found.")

    # 1. Same-building internal routing
    if start_loc.get("building_id") and start_loc.get("building_id") == end_loc.get("building_id"):
        if start_loc["floor"] == end_loc["floor"]:
            return {
                "start": start_loc,
                "end": end_loc,
                "path": [[start_loc["lng"], start_loc["lat"]], [end_loc["lng"], end_loc["lat"]]],
                "instructions": [f"Walk directly from {start_loc['name']} to {end_loc['name']} on Floor {start_loc['floor']}."],
                "distance_deg": get_distance((start_loc["lat"], start_loc["lng"]), (end_loc["lat"], end_loc["lng"]))
            }
        else:
            # Different floors: route via Lift/Steps
            conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT room_id, coordinate_x as lat, coordinate_y as lng FROM Rooms WHERE building_id = %s AND (room_id LIKE '%%LIFT%%' OR room_id LIKE '%%STEPS%%' OR room_type = 'Corridor') LIMIT 1", (start_loc["building_id"],))
            transit = cursor.fetchone()
            conn.close()
            
            if transit:
                transit_name = transit["room_id"]
                transit_lat = transit["lat"]
                transit_lng = transit["lng"]
                return {
                    "start": start_loc,
                    "end": end_loc,
                    "path": [
                        [start_loc["lng"], start_loc["lat"]],
                        [transit_lng, transit_lat],
                        [end_loc["lng"], end_loc["lat"]]
                    ],
                    "instructions": [
                        f"Walk from {start_loc['name']} to the transit ({transit_name}) on Floor {start_loc['floor']}.",
                        f"Take the transit to Floor {end_loc['floor']}.",
                        f"Exit the transit and walk to {end_loc['name']}."
                    ],
                    "distance_deg": get_distance((start_loc["lat"], start_loc["lng"]), (transit_lat, transit_lng)) + get_distance((transit_lat, transit_lng), (end_loc["lat"], end_loc["lng"]))
                }

    # 2. Outdoor different-building routing
    # Resolve exact coordinates for building entrances
    start_ent_lat, start_ent_lng = start_loc["lat"], start_loc["lng"]
    if start_loc.get("building_id"):
        conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT entrance_x, entrance_y FROM Buildings WHERE building_id = %s", (start_loc["building_id"],))
        b_ent = cursor.fetchone()
        conn.close()
        if b_ent and b_ent["entrance_x"] and b_ent["entrance_y"]:
            start_ent_lat, start_ent_lng = b_ent["entrance_x"], b_ent["entrance_y"]

    end_ent_lat, end_ent_lng = end_loc["lat"], end_loc["lng"]
    if end_loc.get("building_id"):
        conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT entrance_x, entrance_y FROM Buildings WHERE building_id = %s", (end_loc["building_id"],))
        b_ent = cursor.fetchone()
        conn.close()
        if b_ent and b_ent["entrance_x"] and b_ent["entrance_y"]:
            end_ent_lat, end_ent_lng = b_ent["entrance_x"], b_ent["entrance_y"]

    # Match entrance to the nearest walkway node
    start_node = None
    if start_loc.get("building_id") in BUILDING_TO_NODE:
        start_node = BUILDING_TO_NODE[start_loc["building_id"]]
    else:
        start_node = find_closest_node(start_ent_lat, start_ent_lng)

    end_node = None
    if end_loc.get("building_id") in BUILDING_TO_NODE:
        end_node = BUILDING_TO_NODE[end_loc["building_id"]]
    else:
        end_node = find_closest_node(end_ent_lat, end_ent_lng)

    cost, walkway_path_nodes = dijkstra(start_node, end_node)
    
    path_coords = []
    
    # 1. Start from the exact starting room / coordinate
    path_coords.append([start_loc["lng"], start_loc["lat"]])
    
    # 2. Add building entrance (if starting from a room inside a building)
    if start_loc["type"] == "room":
        path_coords.append([start_ent_lng, start_ent_lat])
        
    # 3. Add all walkway nodes
    for node in walkway_path_nodes:
        lat, lng = WALKWAY_NODES[node]
        path_coords.append([lng, lat])
        
    # 4. Add destination building entrance (if ending in a room inside a building)
    if end_loc["type"] == "room":
        path_coords.append([end_ent_lng, end_ent_lat])
        
    # 5. Add exact destination room / coordinate
    path_coords.append([end_loc["lng"], end_loc["lat"]])
    
    filtered_coords = []
    for coord in path_coords:
        if not filtered_coords or filtered_coords[-1] != coord:
            filtered_coords.append(coord)
            
    instructions = []
    if start_loc["type"] == "room":
        if start_loc["floor"] > 0:
            instructions.append(f"Exit room {start_loc['name']} on Floor {start_loc['floor']} and take elevator/stairs to Ground level.")
        instructions.append(f"Exit {start_loc['building_name']} via the main entrance.")
        
    instructions.append("Follow the outdoor walkway paths.")
    
    if end_loc["type"] == "room":
        instructions.append(f"Enter {end_loc['building_name']} via the entrance.")
        if end_loc["floor"] > 0:
            instructions.append(f"Take elevator/stairs to Floor {end_loc['floor']} and locate room {end_loc['name']}.")
        else:
            instructions.append(f"Locate room {end_loc['name']} on the Ground level.")
    else:
        instructions.append(f"Arrive at {end_loc['name']}.")
        
    return {
        "start": start_loc,
        "end": end_loc,
        "path": filtered_coords,
        "instructions": instructions,
        "distance_deg": cost
    }

# --- POST ENDPOINTS (Admin Saves) ---
@app.post("/admin/building")
def add_building(b: BuildingModel):
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("INSERT INTO Buildings (name, total_floors, entrance_x, entrance_y, icon, color, footprint_coordinates) VALUES (%s, %s, %s, %s, %s, %s, %s)", (b.name, b.total_floors, b.entrance_x, b.entrance_y, b.icon, b.color, b.footprint_coordinates))
    conn.commit(); conn.close(); return {"msg": "Saved"}

@app.post("/admin/room")
def add_room(r: RoomModel):
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("INSERT INTO Rooms (room_id, building_id, floor_level, room_type, branch, coordinate_x, coordinate_y, footprint_coordinates, z_coordinate, color) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE building_id=VALUES(building_id), floor_level=VALUES(floor_level), room_type=VALUES(room_type), branch=VALUES(branch), coordinate_x=VALUES(coordinate_x), coordinate_y=VALUES(coordinate_y), footprint_coordinates=VALUES(footprint_coordinates), z_coordinate=VALUES(z_coordinate), color=VALUES(color)", (r.room_id, r.building_id, r.floor_level, r.room_type, r.branch, r.coordinate_x, r.coordinate_y, r.footprint_coordinates, r.z_coordinate, r.color))
    conn.commit(); conn.close(); return {"msg": "Saved"}

@app.post("/admin/status")
def add_message(m: MessageModel):
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("INSERT INTO SystemStatus (message, type) VALUES (%s, %s)", (m.message, m.type))
    conn.commit(); conn.close(); return {"msg": "Saved"}

# --- DELETE ENDPOINTS (Admin Removes) ---
@app.delete("/admin/building/{id}")
def del_building(id: int):
    conn = get_db_connection(); cursor = conn.cursor(); cursor.execute("DELETE FROM Buildings WHERE building_id=%s", (id,)); conn.commit(); conn.close(); return {"msg": "Deleted"}

@app.delete("/admin/room/{id}")
def del_room(id: str):
    conn = get_db_connection(); cursor = conn.cursor(); cursor.execute("DELETE FROM Rooms WHERE room_id=%s", (id,)); conn.commit(); conn.close(); return {"msg": "Deleted"}

@app.delete("/admin/status/{id}")
def del_message(id: int):
    conn = get_db_connection(); cursor = conn.cursor(); cursor.execute("DELETE FROM SystemStatus WHERE status_id=%s", (id,)); conn.commit(); conn.close(); return {"msg": "Deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)