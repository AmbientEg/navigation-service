

```
indoor_navigation_backend/
│
├─ app/
│   ├─ main.py             # FastAPI app entrypoint
│   ├─ database.py         # DB connection
│   ├─ models.py           # SQLAlchemy models
│   ├─ schemas.py          # Pydantic schemas
│   ├─ crud.py             # DB operations
│   ├─ routes/
│   │   ├─ map_routes.py       # floor/building/POI APIs
│   │   ├─ positioning_routes.py # live position APIs
│   │   └─ navigation_routes.py # route calculation APIs
│   └─ services/
│       ├─ routing_service.py   # Dijkstra/A* implementation
│       └─ positioning_service.py
│
├─ requirements.txt
└─ alembic/ (optional for migrations)
```


Dependencies
```
pip install fastapi uvicorn[standard] sqlalchemy asyncpg psycopg2-binary pydantic geoalchemy2 networkx
```
- FastAPI → backend framework
- SQLAlchemy + asyncpg → DB + async support
- GeoAlchemy2 → spatial support for PostGIS
- NetworkX → graph algorithms (A*/Dijkstra) for routing


Database Setup (PostgreSQL + PostGIS)

```
CREATE DATABASE indoor_navigation;
\c indoor_navigation

-- Enable PostGIS
CREATE EXTENSION postgis;

-- Example table
CREATE TABLE floors (
    id UUID PRIMARY KEY,
    building_id UUID,
    level_number INT,
    name TEXT,
    height_meters FLOAT,
    floor_geojson JSONB
);
```



Refrences :
https://eng-badrqabbari.medium.com/using-dijkstras-algorithm-for-indoor-navigation-in-a-flutter-app-3d346c0ede23
https://www.researchgate.net/publication/349495339_A_New_Approach_to_Measuring_the_Similarity_of_Indoor_Semantic_Trajectories
https://www.researchgate.net/publication/341465979_The_Construction_of_a_Network_for_Indoor_Navigation

