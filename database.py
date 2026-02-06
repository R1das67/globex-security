import sqlite3
import os

def connect_db():
    """Stellt die Verbindung zur Datenbank her und sorgt für einen sicheren Speicherort."""
    # Erstellt einen 'data' Ordner, falls nicht vorhanden (wichtig für Server)
    if not os.path.exists("data"):
        os.makedirs("data")
    
    # Datenbank liegt sicher im Unterordner
    return sqlite3.connect("data/globex_v2.db")

def init_db():
    """Initialisiert alle Tabellen. Fügt log_status und log_channel hinzu."""
    conn = connect_db()
    cursor = conn.cursor()
    
    # Tabelle für Einstellungen (Status, Strafen & Logging)
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        guild_id INTEGER PRIMARY KEY,
        anti_invite_status INTEGER DEFAULT 0, anti_invite_punish TEXT DEFAULT 'kick',
        anti_ping_status INTEGER DEFAULT 0, anti_ping_punish TEXT DEFAULT 'kick',
        anti_webhook_status INTEGER DEFAULT 0, anti_webhook_punish TEXT DEFAULT 'kick',
        channel_create_status INTEGER DEFAULT 0, channel_create_punish TEXT DEFAULT 'kick',
        channel_delete_status INTEGER DEFAULT 0, channel_delete_punish TEXT DEFAULT 'kick',
        role_create_status INTEGER DEFAULT 0, role_create_punish TEXT DEFAULT 'kick',
        role_delete_status INTEGER DEFAULT 0, role_delete_punish TEXT DEFAULT 'kick',
        anti_bot_status INTEGER DEFAULT 0, anti_bot_punish TEXT DEFAULT 'kick',
        log_status INTEGER DEFAULT 0, 
        log_channel TEXT DEFAULT 'Not yet processed'
    )''')

    # Tabelle für Limits (Anzahl und Zeiträume)
    cursor.execute('''CREATE TABLE IF NOT EXISTS limits (
        guild_id INTEGER PRIMARY KEY,
        invite_limit INTEGER, invite_time INTEGER,
        ping_limit INTEGER, ping_time INTEGER,
        webhook_limit INTEGER,
        bot_limit INTEGER
    )''')

    # Tabelle für Listen (Whitelist, Blacklist, Trusted)
    cursor.execute('''CREATE TABLE IF NOT EXISTS lists (
        guild_id INTEGER,
        user_id INTEGER,
        list_type TEXT,
        PRIMARY KEY (guild_id, user_id, list_type)
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Globex Database: Tables initialized in /data folder.")

def get_data(table, guild_id):
    """Holt Daten für einen Server. Erstellt Zeile, falls nicht existent."""
    conn = connect_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT * FROM {table} WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    
    if not row:
        # Falls kein Eintrag existiert, neu anlegen
        conn.execute(f"INSERT OR IGNORE INTO {table} (guild_id) VALUES (?)", (guild_id,))
        conn.commit()
        cursor.execute(f"SELECT * FROM {table} WHERE guild_id = ?", (guild_id,))
        row = cursor.fetchone()
    
    data = dict(row)
    conn.close()
    return data

def update_db(table, guild_id, column, value):
    """Aktualisiert einen spezifischen Wert in der Datenbank."""
    conn = connect_db()
    # Sicherstellen, dass der Server existiert
    get_data(table, guild_id)
    conn.execute(f"UPDATE {table} SET {column} = ? WHERE guild_id = ?", (value, guild_id))
    conn.commit()
    conn.close()

def add_to_list(guild_id, user_id, list_type):
    """Fügt eine ID zu einer Liste hinzu (Whitelist/Blacklist/Trusted)."""
    conn = connect_db()
    conn.execute("INSERT OR IGNORE INTO lists (guild_id, user_id, list_type) VALUES (?, ?, ?)", 
                 (guild_id, user_id, list_type))
    conn.commit()
    conn.close()

def remove_from_list(guild_id, user_id, list_type):
    """Entfernt eine ID von einer Liste."""
    conn = connect_db()
    conn.execute("DELETE FROM lists WHERE guild_id = ? AND user_id = ? AND list_type = ?", 
                 (guild_id, user_id, list_type))
    conn.commit()
    conn.close()

def is_on_list(guild_id, user_id, list_type):
    """Prüft, ob eine ID auf einer Liste steht."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM lists WHERE guild_id = ? AND user_id = ? AND list_type = ?", 
                   (guild_id, user_id, list_type))
    res = cursor.fetchone()
    conn.close()
    return res is not None

# Startet die Initialisierung automatisch
init_db()