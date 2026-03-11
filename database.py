import motor.motor_asyncio
import os
import asyncio

# Wir laden die URL aus den Railway-Variablen
MONGO_URL = os.getenv("MONGO_URL")

# Verbindung zum Cluster herstellen
cluster = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
# Wir definieren die Datenbank "GlobexData"
db = cluster["GlobexData"]

async def get_data(category, guild_id):
    """Holt Daten für einen Server aus einer bestimmten Collection."""
    collection = db[category]
    data = await collection.find_one({"_id": str(guild_id)})
    return data if data else {}

async def update_data(category, guild_id, key, value):
    """Aktualisiert oder erstellt einen Wert in der Datenbank."""
    collection = db[category]
    await collection.update_one(
        {"_id": str(guild_id)},
        {"$set": {key: value}},
        upsert=True
    )

async def is_on_list(guild_id, user_id, list_type):
    """Prüft, ob eine User-ID in einer Liste (z.B. Whitelist) steht."""
    collection = db[list_type]
    data = await collection.find_one({"_id": str(guild_id)})
    if data and str(user_id) in data.get("users", []):
        return True
    return False

async def add_to_list(guild_id, user_id, list_type):
    """Fügt einen User zu einer Liste hinzu (ohne Dubletten)."""
    collection = db[list_type]
    await collection.update_one(
        {"_id": str(guild_id)},
        {"$addToSet": {"users": str(user_id)}},
        upsert=True
    )

async def remove_from_list(guild_id, user_id, list_type):
    """Entfernt einen User aus einer Liste."""
    collection = db[list_type]
    await collection.update_one(
        {"_id": str(guild_id)},
        {"$pull": {"users": str(user_id)}}
    )
