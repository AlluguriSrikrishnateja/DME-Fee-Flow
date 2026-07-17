import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "medical_fee.db")

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and creates the Result_Grid table if it doesn't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS Result_Grid (
        PROCEDURE_CD TEXT,
        STATE_CD TEXT,
        PRICING_YEAR INTEGER,
        ALLOWANCE_AMT REAL,
        PROCD_MOD_CD1 TEXT,
        PROCD_MOD_EFF_DT1 TEXT,
        PROCD_MOD_CD2 TEXT,
        PROCD_MOD_EFF_DT2 TEXT,
        PRIMARY KEY (PROCEDURE_CD, STATE_CD, PRICING_YEAR, PROCD_MOD_CD1, PROCD_MOD_CD2)
    );
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
    print("Database initialized successfully at:", DB_PATH)

def upsert_records(records):
    """
    Executes the 'Merge' logic. 
    Appends if the data is new, updates ALLOWANCE_AMT and effect dates if the record already exists.
    """
    query = """
    INSERT INTO Result_Grid (
        PROCEDURE_CD, STATE_CD, PRICING_YEAR, ALLOWANCE_AMT,
        PROCD_MOD_CD1, PROCD_MOD_EFF_DT1, PROCD_MOD_CD2, PROCD_MOD_EFF_DT2
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(PROCEDURE_CD, STATE_CD, PRICING_YEAR, PROCD_MOD_CD1, PROCD_MOD_CD2) 
    DO UPDATE SET
        ALLOWANCE_AMT = excluded.ALLOWANCE_AMT,
        PROCD_MOD_EFF_DT1 = excluded.PROCD_MOD_EFF_DT1,
        PROCD_MOD_EFF_DT2 = excluded.PROCD_MOD_EFF_DT2;
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(query, records)
        conn.commit()
        return conn.total_changes

if __name__ == "__main__":
    init_db()