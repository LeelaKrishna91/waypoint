from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ⚠️ UPDATE THIS LINE: Change 'root' and 'password' to your actual MySQL username and password.
# If your database is named something other than WAYPOINT_RIT, change that too!
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:leela@localhost:3306/" \
""

# Create the engine that drives the connection
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for your database models
Base = declarative_base()