import motor.motor_asyncio
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Verbindung zu MongoDB Atlas (URL kommt aus den Railway-Secrets)
MONGO_URL = os.getenv("MONGO_URL")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client["globex_v2"] # Name der Datenbank

# --- Hilfs-Funktion für den synchronen Aufruf ---
def run_async(coro):
    """Ermöglicht es, asynchrone DB-Abfragen in deinem synchronen Bot zu nutzen."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def init_db():
    """Bei MongoDB nicht zwingend nötig, da Collections automatisch erstellt werden."""
    print("✅ Globex MongoDB: Connection initialized.")

def get_data(table, guild_id):
    """Holt Daten für einen Server. Erstellt Dokument, falls nicht existent."""
    async def _get():
        collection = db[table]
        row = await collection.find_one({"guild_id": guild_id})
        
        if not row:
            # Standardwerte wie in deiner SQLite-Tabelle
            default_entry = {"guild_id": guild_id}
            # Falls es die Settings-Tabelle ist, Standardwerte setzen
            if table == "settings":
                default_entry.update({"anti_ping_direct": "Direct", "log_channel": "Not yet processed"})
            elif table == "adm_timer":
                default_entry.update({"adm_status": 0, "give_time_1": "00:00", "remove_time_1": "00:00"})
            
            await collection.insert_one(default_entry)
            row = default_entry
        
        return dict(row)

    return run_async(_get())

def update_db(table, guild_id, column, value):
    """Aktualisiert einen spezifischen Wert."""
    async def _update():
        collection = db[table]
        # Falls das Dokument noch nicht existiert, wird es durch get_data() in deinen Menüs eh erstellt
        await collection.update_one(
            {"guild_id": guild_id},
            {"$set": {column: value}},
            upsert=True
        )

    run_async(_update())

def add_to_list(guild_id, user_id, list_type):
    """Fügt User zur Whitelist/Blacklist hinzu."""
    async def _add():
        collection = db["lists"]
        await collection.update_one(
            {"guild_id": guild_id, "user_id": user_id, "list_type": list_type},
            {"$set": {"guild_id": guild_id, "user_id": user_id, "list_type": list_type}},
            upsert=True
        )

    run_async(_add())

def remove_from_list(guild_id, user_id, list_type):
    """Entfernt User von einer Liste."""
    async def _remove():
        collection = db["lists"]
        await collection.delete_one({"guild_id": guild_id, "user_id": user_id, "list_type": list_type})

    run_async(_remove())

def is_on_list(guild_id, user_id, list_type):
    """Prüft auf Listen-Eintrag."""
    async def _check():
        collection = db["lists"]
        res = await collection.find_one({"guild_id": guild_id, "user_id": user_id, "list_type": list_type})
        return res is not None

    return run_async(_check())

# Initialisierung beim Import
init_db()