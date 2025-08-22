from fastapi import FastAPI
from contextlib import asynccontextmanager
from helpers.config import get_settings
from routes import data, data_multiple
from motor.motor_asyncio import AsyncIOMotorClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    print("✅ Loaded settings:", settings.model_dump())

    app.mongo_conn = AsyncIOMotorClient(settings.MONGODB_URL)
    app.db_client = app.mongo_conn[settings.MONGODB_DB]

    print("✅ Connected to MongoDB")
    print("✅ Application started successfully")

    # Yield control to the application

    yield

    # Shutdown  
    print("👋 Shutting down...")
    app.mongo_conn.close()
    print("❌ MongoDB connection closed")


app = FastAPI(lifespan=lifespan)

# Include routes
app.include_router(data.data_router)
app.include_router(data_multiple.data_router)
