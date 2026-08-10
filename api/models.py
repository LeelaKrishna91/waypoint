from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base

class Building(Base):
    __tablename__ = "Buildings"
    building_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    total_floors = Column(Integer, nullable=False)
    entrance_x = Column(Float, nullable=True)
    entrance_y = Column(Float, nullable=True)
    
    icon = Column(String(50), default="fa-building")
    color = Column(String(20), default="#3b82f6")
    
    # 🚨 NEW: Stores your custom 3D shape array!
    footprint_coordinates = Column(String(2000), nullable=True)
    
    rooms = relationship("Room", back_populates="building", cascade="all, delete-orphan")

class Room(Base):
    __tablename__ = "Rooms"
    room_id = Column(String(50), primary_key=True, index=True)
    building_id = Column(Integer, ForeignKey("Buildings.building_id", ondelete="CASCADE"), nullable=False)
    floor_level = Column(Integer, nullable=False)
    room_type = Column(String(50))
    branch = Column(String(100))
    class_in_charge = Column(String(100))
    coordinate_x = Column(Float, nullable=False)
    coordinate_y = Column(Float, nullable=False)
    floor_plan_image = Column(String(255), nullable=False, default="campus_map.png")
    footprint_coordinates = Column(String(2000), nullable=True)
    z_coordinate = Column(Float, default=3.5)
    building = relationship("Building", back_populates="rooms")
    events = relationship("Event", back_populates="room", cascade="all, delete-orphan")

class Event(Base):
    __tablename__ = "Events"
    event_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_id = Column(String(50), ForeignKey("Rooms.room_id", ondelete="CASCADE"), nullable=False)
    event_name = Column(String(200), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    room = relationship("Room", back_populates="events")

class SystemStatus(Base):
    __tablename__ = "SystemStatus"
    status_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    message = Column(String(255), nullable=False)
    type = Column(String(50), default="info")
    is_active = Column(Integer, default=1)
    created_at = Column(String(50), nullable=True)