import os
import json
import mysql.connector
from mysql.connector import errorcode

# Load configuration from environment variables
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "leela")
DB_DATABASE = os.environ.get("DB_DATABASE", "waypoint_rit")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))

print(f"Connecting to database: {DB_HOST}:{DB_PORT} as {DB_USER}...")

try:
    # First, try to connect without database to create it if it doesn't exist
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_DATABASE}")
    conn.close()
    
    # Reconnect with the database selected
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_DATABASE,
        port=DB_PORT
    )
    cursor = conn.cursor()
    print("Successfully connected to database!")

    # Create tables
    print("Creating tables...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Buildings (
        building_id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) UNIQUE NOT NULL,
        total_floors INT NOT NULL,
        entrance_x FLOAT,
        entrance_y FLOAT,
        icon VARCHAR(50) DEFAULT 'fa-building',
        color VARCHAR(20) DEFAULT '#3b82f6',
        footprint_coordinates TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Rooms (
        room_id VARCHAR(50) PRIMARY KEY,
        building_id INT NOT NULL,
        floor_level INT NOT NULL,
        room_type VARCHAR(50),
        branch VARCHAR(100),
        class_in_charge VARCHAR(100),
        coordinate_x FLOAT NOT NULL,
        coordinate_y FLOAT NOT NULL,
        floor_plan_image VARCHAR(255) NOT NULL DEFAULT 'campus_map.png',
        footprint_coordinates TEXT,
        color VARCHAR(50) DEFAULT NULL,
        z_coordinate FLOAT DEFAULT 3.5,
        FOREIGN KEY (building_id) REFERENCES Buildings(building_id) ON DELETE CASCADE
    )
    """)
    try:
        cursor.execute("ALTER TABLE Rooms ADD COLUMN color VARCHAR(50) DEFAULT NULL")
        print("Successfully added color column to Rooms table.")
    except mysql.connector.Error as err:
        if err.errno != mysql.connector.errorcode.ER_DUP_FIELDNAME:
            raise err
    conn.commit()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS SystemStatus (
        status_id INT PRIMARY KEY AUTO_INCREMENT,
        message VARCHAR(255) NOT NULL,
        type VARCHAR(50) DEFAULT 'info',
        is_active INT DEFAULT 1,
        created_at VARCHAR(50)
    )
    """)
    conn.commit()

    # Load and seed Buildings
    buildings_file = os.path.join(os.path.dirname(__file__), "exports", "buildings.json")
    if os.path.exists(buildings_file):
        print("Seeding Buildings...")
        with open(buildings_file, "r") as f:
            buildings = json.load(f)
        for b in buildings:
            cursor.execute("""
            INSERT INTO Buildings (building_id, name, total_floors, entrance_x, entrance_y, icon, color, footprint_coordinates)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                name=VALUES(name), total_floors=VALUES(total_floors), entrance_x=VALUES(entrance_x),
                entrance_y=VALUES(entrance_y), icon=VALUES(icon), color=VALUES(color),
                footprint_coordinates=VALUES(footprint_coordinates)
            """, (b.get("building_id"), b.get("name"), b.get("total_floors"), b.get("entrance_x"), b.get("entrance_y"), b.get("icon"), b.get("color"), b.get("footprint_coordinates")))
        conn.commit()
        print(f"Seeded {len(buildings)} buildings.")

    # Load and seed Rooms
    rooms_file = os.path.join(os.path.dirname(__file__), "exports", "rooms.json")
    if os.path.exists(rooms_file):
        print("Seeding Rooms...")
        with open(rooms_file, "r") as f:
            rooms = json.load(f)
        for r in rooms:
            cursor.execute("""
             INSERT INTO Rooms (room_id, building_id, floor_level, room_type, branch, class_in_charge, coordinate_x, coordinate_y, floor_plan_image, footprint_coordinates, z_coordinate, color)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
             ON DUPLICATE KEY UPDATE 
                 building_id=VALUES(building_id), floor_level=VALUES(floor_level), room_type=VALUES(room_type),
                 branch=VALUES(branch), class_in_charge=VALUES(class_in_charge), coordinate_x=VALUES(coordinate_x),
                 coordinate_y=VALUES(coordinate_y), floor_plan_image=VALUES(floor_plan_image),
                 footprint_coordinates=VALUES(footprint_coordinates), z_coordinate=VALUES(z_coordinate), color=VALUES(color)
             """, (r.get("room_id"), r.get("building_id"), r.get("floor_level"), r.get("room_type"), r.get("branch"), r.get("class_in_charge"), r.get("coordinate_x"), r.get("coordinate_y"), r.get("floor_plan_image"), r.get("footprint_coordinates"), r.get("z_coordinate"), r.get("color")))
        conn.commit()
        print(f"Seeded {len(rooms)} rooms.")

    # Load and seed SystemStatus
    status_file = os.path.join(os.path.dirname(__file__), "exports", "systemstatus.json")
    if os.path.exists(status_file):
        print("Seeding SystemStatus...")
        with open(status_file, "r") as f:
            statuses = json.load(f)
        for s in statuses:
            cursor.execute("""
            INSERT INTO SystemStatus (status_id, message, type, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                message=VALUES(message), type=VALUES(type), is_active=VALUES(is_active), created_at=VALUES(created_at)
            """, (s.get("status_id"), s.get("message"), s.get("type"), s.get("is_active"), s.get("created_at")))
        conn.commit()
        print(f"Seeded {len(statuses)} system status messages.")

    conn.close()
    print("Migration completed successfully!")

except mysql.connector.Error as err:
    print(f"Database error: {err}")
except Exception as e:
    print(f"Unexpected error: {e}")
