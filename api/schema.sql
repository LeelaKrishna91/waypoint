CREATE TABLE Rooms (
    room_id VARCHAR(50) PRIMARY KEY,
    building_id INT NOT NULL,
    floor_level INT NOT NULL,
    room_type VARCHAR(50),
    branch VARCHAR(100),
    class_in_charge VARCHAR(100), -- 🚨 Added this back in
    coordinate_x FLOAT NOT NULL,
    coordinate_y FLOAT NOT NULL,
    floor_plan_image VARCHAR(255) NOT NULL DEFAULT 'campus_map.png',
    footprint_coordinates TEXT,
    z_coordinate FLOAT DEFAULT 3.5,
    FOREIGN KEY (building_id) REFERENCES Buildings(building_id) ON DELETE CASCADE
);