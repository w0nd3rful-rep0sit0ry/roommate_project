#!/usr/bin/env python3
"""
Telegram Housing Search WebApp Backend
FastAPI + Telegram Bot + MongoDB + Web Scraping
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import json
import hashlib
import time

from fastapi import FastAPI, HTTPException, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import motor.motor_asyncio
from pymongo import IndexModel, GEOSPHERE
import httpx
from geopy.distance import geodesic
import requests
from bs4 import BeautifulSoup
import random

# Initialize FastAPI app
app = FastAPI(
    title="Telegram Housing Search API",
    version="1.0.0",
    description="API for Telegram webapp housing search in Moscow"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "telegram_housing_db")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "moscow_housing_secret_2025")

# Global variables
mongodb_client = None
mongodb = None

# Pydantic Models
class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int

class UserProfile(BaseModel):
    telegram_id: int
    name: str
    photo_url: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    about: Optional[str] = None
    preferred_location: Optional[str] = None
    search_radius_km: float = 2.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class MetroStation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    name_en: Optional[str] = None
    location: Dict[str, float]  # {"type": "Point", "coordinates": [lon, lat]}
    line: str
    line_color: str

class PropertyListing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    price: float
    location: Dict[str, float]  # GeoJSON Point
    address: str
    area: Optional[float] = None
    rooms: Optional[int] = None
    property_type: Optional[str] = None
    description: Optional[str] = None
    contact_info: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    source_url: Optional[str] = None
    distance_to_metro: Optional[float] = None
    liked_by: List[int] = Field(default_factory=list)  # Telegram user IDs

class GeospatialFilter(BaseModel):
    center: List[float]  # [lon, lat]
    radius_km: float
    property_type: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    rooms: Optional[List[int]] = None

class LikePropertyRequest(BaseModel):
    property_id: str
    telegram_id: int

# Database setup
@app.on_event("startup")
async def startup_db_client():
    global mongodb_client, mongodb
    mongodb_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
    mongodb = mongodb_client[DB_NAME]
    
    # Create geospatial indexes
    await mongodb.metro_stations.create_index([("location", GEOSPHERE)])
    await mongodb.properties.create_index([("location", GEOSPHERE)])
    
    # Load initial metro stations data
    await load_moscow_metro_stations()
    print("✅ Database connected and metro stations loaded")

@app.on_event("shutdown")
async def shutdown_db_client():
    if mongodb_client:
        mongodb_client.close()

# Moscow Metro Stations Data
MOSCOW_METRO_STATIONS = [
    {
        "name": "Сокольники",
        "name_en": "Sokolniki",
        "coordinates": [37.6799, 55.7886],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Красносельская",
        "name_en": "Krasnoselskaya",
        "coordinates": [37.6656, 55.7797],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Комсомольская",
        "name_en": "Komsomolskaya",
        "coordinates": [37.6544, 55.7744],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Красные ворота",
        "name_en": "Krasnye Vorota",
        "coordinates": [37.6479, 55.7687],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Чистые пруды",
        "name_en": "Chistye Prudy",
        "coordinates": [37.6384, 55.7648],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Лубянка",
        "name_en": "Lubyanka",
        "coordinates": [37.6282, 55.7581],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Охотный ряд",
        "name_en": "Okhotny Ryad",
        "coordinates": [37.6155, 55.7573],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Библиотека имени Ленина",
        "name_en": "Biblioteka imeni Lenina",
        "coordinates": [37.6109, 55.7515],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Кропоткинская",
        "name_en": "Kropotkinskaya",
        "coordinates": [37.6035, 55.7456],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Парк культуры",
        "name_en": "Park Kultury",
        "coordinates": [37.5936, 55.7355],
        "line": "Сокольническая",
        "line_color": "#D50000"
    },
    {
        "name": "Новокузнецкая",
        "name_en": "Novokuznetskaya",
        "coordinates": [37.6291, 55.7425],
        "line": "Замоскворецкая",
        "line_color": "#4CAF50"
    },
    {
        "name": "Третьяковская",
        "name_en": "Tretyakovskaya",
        "coordinates": [37.6252, 55.7406],
        "line": "Замоскворецкая",
        "line_color": "#4CAF50"
    },
    {
        "name": "Театральная",
        "name_en": "Teatralnaya",
        "coordinates": [37.6201, 55.7581],
        "line": "Замоскворецкая",
        "line_color": "#4CAF50"
    },
    {
        "name": "Тверская",
        "name_en": "Tverskaya",
        "coordinates": [37.6054, 55.7669],
        "line": "Замоскворецкая",
        "line_color": "#4CAF50"
    },
    {
        "name": "Маяковская",
        "name_en": "Mayakovskaya",
        "coordinates": [37.5959, 55.7696],
        "line": "Замоскворецкая",
        "line_color": "#4CAF50"
    }
]

async def load_moscow_metro_stations():
    """Load Moscow metro stations into database"""
    try:
        existing_count = await mongodb.metro_stations.count_documents({})
        if existing_count > 0:
            print(f"Metro stations already loaded: {existing_count} stations")
            return

        stations = []
        for station_data in MOSCOW_METRO_STATIONS:
            station = MetroStation(
                name=station_data["name"],
                name_en=station_data.get("name_en"),
                location={
                    "type": "Point",
                    "coordinates": station_data["coordinates"]
                },
                line=station_data["line"],
                line_color=station_data["line_color"]
            )
            stations.append(station.dict())

        if stations:
            await mongodb.metro_stations.insert_many(stations)
            print(f"✅ Loaded {len(stations)} metro stations")
    except Exception as e:
        print(f"❌ Error loading metro stations: {e}")

# Property scraping from Cian.ru (simplified version)
async def scrape_cian_properties(location: str, radius_km: float) -> List[Dict]:
    """Scrape property listings from Cian.ru"""
    try:
        # Simulate property listings (in production, implement actual scraping)
        mock_properties = [
            {
                "title": "2-комнатная квартира, 65 м²",
                "price": 85000,
                "coordinates": [37.6176 + random.uniform(-0.01, 0.01), 55.7558 + random.uniform(-0.01, 0.01)],
                "address": "ул. Тверская, 12",
                "area": 65,
                "rooms": 2,
                "description": "Уютная квартира в центре Москвы",
                "contact_info": "+7 (495) 123-45-67",
                "images": [],
                "source_url": "https://www.cian.ru/rent/flat/123456/"
            },
            {
                "title": "1-комнатная квартира, 42 м²",
                "price": 55000,
                "coordinates": [37.6156 + random.uniform(-0.01, 0.01), 55.7548 + random.uniform(-0.01, 0.01)],
                "address": "ул. Арбат, 25",
                "area": 42,
                "rooms": 1,
                "description": "Светлая квартира недалеко от метро",
                "contact_info": "+7 (495) 987-65-43",
                "images": [],
                "source_url": "https://www.cian.ru/rent/flat/789012/"
            },
            {
                "title": "3-комнатная квартира, 95 м²",
                "price": 120000,
                "coordinates": [37.6200 + random.uniform(-0.01, 0.01), 55.7580 + random.uniform(-0.01, 0.01)],
                "address": "Большая Никитская, 7",
                "area": 95,
                "rooms": 3,
                "description": "Просторная квартира с видом на город",
                "contact_info": "+7 (495) 555-77-88",
                "images": [],
                "source_url": "https://www.cian.ru/rent/flat/345678/"
            }
        ]

        # Add more properties around different metro stations
        for station in MOSCOW_METRO_STATIONS[:5]:  # First 5 stations
            for i in range(2):  # 2 properties per station
                mock_properties.append({
                    "title": f"{random.choice(['1', '2', '3'])}-комнатная квартира, {random.randint(35, 100)} м²",
                    "price": random.randint(40000, 150000),
                    "coordinates": [
                        station["coordinates"][0] + random.uniform(-0.005, 0.005),
                        station["coordinates"][1] + random.uniform(-0.005, 0.005)
                    ],
                    "address": f"ул. {random.choice(['Московская', 'Центральная', 'Садовая', 'Парковая'])}, {random.randint(1, 50)}",
                    "area": random.randint(35, 100),
                    "rooms": random.randint(1, 3),
                    "description": f"Квартира рядом с метро {station['name']}",
                    "contact_info": f"+7 (495) {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}",
                    "images": [],
                    "source_url": f"https://www.cian.ru/rent/flat/{random.randint(100000, 999999)}/"
                })

        return mock_properties

    except Exception as e:
        print(f"Error scraping properties: {e}")
        return []

# Cache for properties
property_cache = {}
cache_ttl = 1800  # 30 minutes

def get_cache_key(center: List[float], radius: float, filters: Dict) -> str:
    """Generate cache key for property search"""
    key_data = f"{center}_{radius}_{json.dumps(filters, sort_keys=True)}"
    return hashlib.md5(key_data.encode()).hexdigest()

# API Endpoints
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Telegram Housing Search API"}

@app.get("/api/metro-stations")
async def get_metro_stations():
    """Get all Moscow metro stations"""
    try:
        cursor = mongodb.metro_stations.find({})
        stations = []
        async for station in cursor:
            station['_id'] = str(station['_id'])
            stations.append(station)
        return stations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading metro stations: {str(e)}")

@app.post("/api/user/profile")
async def create_or_update_profile(profile: UserProfile):
    """Create or update user profile"""
    try:
        profile.updated_at = datetime.utcnow()
        
        result = await mongodb.user_profiles.update_one(
            {"telegram_id": profile.telegram_id},
            {"$set": profile.dict()},
            upsert=True
        )
        
        return {"success": True, "profile_id": str(result.upserted_id) if result.upserted_id else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving profile: {str(e)}")

@app.get("/api/user/profile/{telegram_id}")
async def get_user_profile(telegram_id: int):
    """Get user profile by Telegram ID"""
    try:
        profile = await mongodb.user_profiles.find_one({"telegram_id": telegram_id})
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        profile['_id'] = str(profile['_id'])
        return profile
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading profile: {str(e)}")

@app.post("/api/properties/search")
async def search_properties(filters: GeospatialFilter, background_tasks: BackgroundTasks):
    """Search properties with geospatial filtering"""
    try:
        # Check cache first
        cache_key = get_cache_key(filters.center, filters.radius_km, filters.dict())
        
        if cache_key in property_cache:
            cached_data = property_cache[cache_key]
            if time.time() - cached_data['timestamp'] < cache_ttl:
                return cached_data['properties']

        # Convert center coordinates to GeoJSON format
        center_point = {
            "type": "Point",
            "coordinates": filters.center
        }

        # Build MongoDB query
        query = {
            "location": {
                "$near": {
                    "$geometry": center_point,
                    "$maxDistance": filters.radius_km * 1000  # Convert to meters
                }
            }
        }

        # Add filters
        if filters.min_price is not None or filters.max_price is not None:
            price_filter = {}
            if filters.min_price is not None:
                price_filter["$gte"] = filters.min_price
            if filters.max_price is not None:
                price_filter["$lte"] = filters.max_price
            query["price"] = price_filter

        if filters.rooms:
            query["rooms"] = {"$in": filters.rooms}

        if filters.property_type:
            query["property_type"] = filters.property_type

        # Search in database
        cursor = mongodb.properties.find(query).limit(50)
        properties = []
        async for prop in cursor:
            prop['_id'] = str(prop['_id'])
            # Calculate distance to center
            prop_coords = prop['location']['coordinates']
            distance = geodesic(
                (filters.center[1], filters.center[0]),  # lat, lon
                (prop_coords[1], prop_coords[0])
            ).kilometers
            prop['distance_to_center'] = round(distance, 2)
            properties.append(prop)

        # If no properties found, scrape new ones
        if not properties:
            background_tasks.add_task(scrape_and_store_properties, filters)
            
            # Return mock data for immediate response
            mock_properties = await scrape_cian_properties("Moscow", filters.radius_km)
            for prop in mock_properties:
                # Check if within radius
                distance = geodesic(
                    (filters.center[1], filters.center[0]),
                    (prop['coordinates'][1], prop['coordinates'][0])
                ).kilometers
                
                if distance <= filters.radius_km:
                    prop['distance_to_center'] = round(distance, 2)
                    prop['location'] = {
                        "type": "Point",
                        "coordinates": prop['coordinates']
                    }
                    properties.append(prop)

        # Cache results
        property_cache[cache_key] = {
            'properties': properties,
            'timestamp': time.time()
        }

        return properties

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching properties: {str(e)}")

async def scrape_and_store_properties(filters: GeospatialFilter):
    """Background task to scrape and store properties"""
    try:
        properties_data = await scrape_cian_properties("Moscow", filters.radius_km)
        
        for prop_data in properties_data:
            property_listing = PropertyListing(
                title=prop_data["title"],
                price=prop_data["price"],
                location={
                    "type": "Point",
                    "coordinates": prop_data["coordinates"]
                },
                address=prop_data["address"],
                area=prop_data.get("area"),
                rooms=prop_data.get("rooms"),
                description=prop_data.get("description"),
                contact_info=prop_data.get("contact_info"),
                images=prop_data.get("images", []),
                source_url=prop_data.get("source_url")
            )
            
            # Insert if not exists
            await mongodb.properties.update_one(
                {"source_url": property_listing.source_url},
                {"$set": property_listing.dict()},
                upsert=True
            )
        
        print(f"✅ Scraped and stored {len(properties_data)} properties")

    except Exception as e:
        print(f"❌ Error in background scraping: {e}")

@app.get("/api/properties/near-metro")
async def get_properties_near_metro(
    station_name: str = Query(..., description="Metro station name"),
    radius_km: float = Query(2.0, description="Search radius in kilometers")
):
    """Get properties near a specific metro station"""
    try:
        # Find metro station
        station = await mongodb.metro_stations.find_one({"name": station_name})
        if not station:
            # Try English name
            station = await mongodb.metro_stations.find_one({"name_en": station_name})
        
        if not station:
            raise HTTPException(status_code=404, detail="Metro station not found")

        # Create filter for the station location
        filters = GeospatialFilter(
            center=station["location"]["coordinates"],
            radius_km=radius_km
        )

        # Search properties
        return await search_properties(filters, BackgroundTasks())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching properties near metro: {str(e)}")

@app.post("/api/properties/{property_id}/like")
async def like_property(property_id: str, request: LikePropertyRequest):
    """Like a property listing"""
    try:
        result = await mongodb.properties.update_one(
            {"id": property_id},
            {"$addToSet": {"liked_by": request.telegram_id}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        return {"success": True, "message": "Property liked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error liking property: {str(e)}")

@app.get("/api/properties/{property_id}/contact")
async def get_property_contact(property_id: str, telegram_id: int):
    """Get property contact information (only for users who liked it)"""
    try:
        property_doc = await mongodb.properties.find_one({"id": property_id})
        
        if not property_doc:
            raise HTTPException(status_code=404, detail="Property not found")
        
        if telegram_id not in property_doc.get("liked_by", []):
            raise HTTPException(status_code=403, detail="You must like the property to see contact information")
        
        return {
            "contact_info": property_doc.get("contact_info"),
            "source_url": property_doc.get("source_url")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting contact info: {str(e)}")

# Telegram WebApp validation
@app.post("/api/telegram/validate")
async def validate_telegram_data(request: Request):
    """Validate Telegram WebApp data"""
    try:
        data = await request.json()
        # In production, implement proper Telegram data validation
        # For now, just return the user data
        return {"valid": True, "user": data.get("user")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Telegram data: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)