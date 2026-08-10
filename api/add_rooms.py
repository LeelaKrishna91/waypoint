import mysql.connector
import json
import math

def get_db():
    return mysql.connector.connect(
        host="localhost", user="root", password="leela", database="waypoint_rit"
    )

LAT_M = 111139.0
LNG_M = 111139.0 * math.cos(math.radians(13.039))

def create_rect(cx, cy, width_m, height_m, angle_deg):
    hw = (width_m / 2.0) / LNG_M
    hh = (height_m / 2.0) / LAT_M
    
    p1 = [-hw, hh]
    p2 = [hw, hh]
    p3 = [hw, -hh]
    p4 = [-hw, -hh]
    
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    
    poly = []
    for p in [p1, p2, p3, p4, p1]:
        rx = p[0]*cos_a - p[1]*sin_a
        ry = p[0]*sin_a + p[1]*cos_a
        poly.append([cx + rx, cy + ry])
    
    return json.dumps([[poly]]) # GeoJSON polygon is an array of rings

start_lng = 80.04576538354922
start_lat = 13.039807863595414

# Wall angle from previous calculation (perpendicular to 4.17 degrees is -85.83)
wall_angle = -85.83

rooms = [
    {"id": "BOYS RESTROOM", "w": 6, "d": 8, "type": "Facility"},
    {"id": "STEPS_7_N", "w": 4, "d": 8, "type": "Corridor"},
    {"id": "C7-05", "w": 10, "d": 12, "type": "Classroom"},
    {"id": "C7-04", "w": 10, "d": 12, "type": "Classroom"},
    {"id": "C7-03", "w": 10, "d": 12, "type": "Classroom"},
    {"id": "C7-02", "w": 10, "d": 12, "type": "Classroom"},
    {"id": "STEPS_7_S", "w": 6, "d": 12, "type": "Corridor"},
    {"id": "STAFF ROOM", "w": 12, "d": 12, "type": "Facility"},
]

conn = get_db()
cursor = conn.cursor()
cursor.execute("SELECT building_id FROM Buildings WHERE name LIKE '%C Block%' LIMIT 1")
res = cursor.fetchone()
b_id = res[0] if res else 1

current_distance = 0.0

for r in rooms:
    center_dist_along = current_distance + (r['w'] / 2.0)
    center_dist_perp = - (r['d'] / 2.0) # Move INSIDE the building (negative depth if right is positive and wall goes south)
    
    rad_along = math.radians(wall_angle)
    dx_along = center_dist_along * math.cos(rad_along)
    dy_along = center_dist_along * math.sin(rad_along)
    
    rad_perp = math.radians(wall_angle - 90)
    dx_perp = center_dist_perp * math.cos(rad_perp)
    dy_perp = center_dist_perp * math.sin(rad_perp)
    
    cx = start_lng + (dx_along + dx_perp) / LNG_M
    cy = start_lat + (dy_along + dy_perp) / LAT_M
    
    footprint = create_rect(cx, cy, r['w'], r['d'], wall_angle)
    
    cursor.execute("DELETE FROM Rooms WHERE room_id = %s", (r['id'],))
    cursor.execute("INSERT INTO Rooms (room_id, building_id, floor_level, room_type, coordinate_x, coordinate_y, footprint_coordinates, z_coordinate) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (r['id'], b_id, 7, r['type'], cx, cy, footprint, 3.5))
    print(f"Added {r['id']}")
    
    current_distance += r['w'] + 0.5 # 0.5 meter gap

# Add LIFT inside STAFF ROOM footprint
cx_lift = cx + (4 * math.cos(math.radians(wall_angle))) / LNG_M
cy_lift = cy + (4 * math.sin(math.radians(wall_angle))) / LAT_M
footprint = create_rect(cx_lift, cy_lift, 4, 4, wall_angle)
cursor.execute("DELETE FROM Rooms WHERE room_id = 'LIFT_7'")
cursor.execute("INSERT INTO Rooms (room_id, building_id, floor_level, room_type, coordinate_x, coordinate_y, footprint_coordinates, z_coordinate) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", ("LIFT_7", b_id, 7, "Facility", cx_lift, cy_lift, footprint, 3.5))
print("Added LIFT_7")

conn.commit()
conn.close()
