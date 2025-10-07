import os
import random
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    """Establishes a connection to the database."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set.")
    result = urlparse(DATABASE_URL)
    conn = psycopg2.connect(
        dbname=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )
    return conn

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        # Keywords and Responses tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id SERIAL PRIMARY KEY,
                keyword_text VARCHAR(255) UNIQUE NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id SERIAL PRIMARY KEY,
                keyword_id INTEGER NOT NULL,
                response_text TEXT NOT NULL,
                FOREIGN KEY (keyword_id) REFERENCES keywords (id) ON DELETE CASCADE
            );
        """)
        # Settings table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(255) PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        # Insert default settings if they don't exist
        default_settings = {
            'flow_enabled': 'true',
            'media_interval_min': '2',
            'media_interval_max': '4',
            'step0_msgs_1': 'Hi, I’m {my_name}\nHello babe, my name is {my_name}',
            'step0_msgs_2': 'How are you, {user_name}?\nHow’s your day going, {user_name}?',
            'step1_msgs': 'You want sex?\nYou want video?\nYou interested?\nLike me?',
            'step2_msg': 'Babe it’s my personal profile link, just free join now then I send my 5 hot video now',
            'fallback_msgs': 'mmh 😏\nso hot...\nu make me wet 💦\nbad boy 😉',
            'cpa_links': 'https://example.com/signup'
        }
        for key, value in default_settings.items():
            cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (key, value))
    conn.commit()
    conn.close()

# --- Settings Functions ---
def get_all_settings():
    """Retrieves all settings as a dictionary."""
    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT key, value FROM settings")
        settings = {row['key']: row['value'] for row in cur.fetchall()}
    conn.close()
    return settings

def update_settings(settings_dict):
    """Updates multiple settings in the database."""
    conn = get_db_connection()
    with conn.cursor() as cur:
        for key, value in settings_dict.items():
            cur.execute("""
                INSERT INTO settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
            """, (key, value))
    conn.commit()
    conn.close()

# --- Keyword/Response Functions ---
def get_random_response(message_text):
    conn = get_db_connection()
    response = None
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT id, keyword_text FROM keywords")
        keywords = cur.fetchall()
        matched_keyword = None
        for kw in keywords:
            if kw['keyword_text'].lower() in message_text.lower():
                matched_keyword = kw
                break
        if matched_keyword:
            cur.execute("SELECT response_text FROM responses WHERE keyword_id = %s", (matched_keyword['id'],))
            responses = cur.fetchall()
            if responses:
                response = random.choice(responses)['response_text']
    conn.close()
    return response

def get_all_keywords_and_responses():
    conn = get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT k.id, k.keyword_text, array_agg(r.response_text) as responses
            FROM keywords k
            LEFT JOIN responses r ON k.id = r.keyword_id
            GROUP BY k.id
            ORDER BY k.keyword_text;
        """)
        data = cur.fetchall()
    conn.close()
    return data

def add_keyword_with_responses(keyword, response_list):
    conn = get_db_connection()
    with conn.cursor() as cur:
        try:
            cur.execute("INSERT INTO keywords (keyword_text) VALUES (%s) RETURNING id", (keyword,))
            keyword_id = cur.fetchone()[0]
            for response_text in response_list:
                if response_text:
                    cur.execute("INSERT INTO responses (keyword_id, response_text) VALUES (%s, %s)", (keyword_id, response_text))
            conn.commit()
        except psycopg2.IntegrityError:
            conn.rollback()
        finally:
            cur.close()
            conn.close()

def delete_keyword(keyword_id):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM keywords WHERE id = %s", (keyword_id,))
    conn.commit()
    conn.close()
