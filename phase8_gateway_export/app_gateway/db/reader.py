import sqlite3
import re
from typing import List, Dict, Any, Tuple

class ReadOnlyDatabase:
    """
    Gateway DB Reader. 
    Strictly enforces No-Mutation policy using multiple defense layers:
    1. URI mode=ro
    2. PRAGMA query_only = ON
    3. sqlite3.set_authorizer
    4. Regex verification
    """
    
    FORBIDDEN_KEYWORDS = re.compile(
        r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|REPLACE|TRUNCATE)\b', 
        re.IGNORECASE
    )

    def __init__(self, db_path: str):
        self.db_path = db_path
        # Defense 1: uri=True enables file:path?mode=ro
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        
        # Defense 2: PRAGMA query_only
        self.conn.execute("PRAGMA query_only = ON")
        
        # Defense 3: sqlite3.set_authorizer
        self.conn.set_authorizer(self._authorizer)

    def _authorizer(self, action: int, arg1: str, arg2: str, dbname: str, source: str) -> int:
        forbidden_actions = {
            sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TABLE, 
            sqlite3.SQLITE_CREATE_TEMP_INDEX, sqlite3.SQLITE_CREATE_TEMP_TABLE, 
            sqlite3.SQLITE_CREATE_TEMP_TRIGGER, sqlite3.SQLITE_CREATE_TEMP_VIEW, 
            sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_CREATE_VIEW, 
            sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_TABLE, 
            sqlite3.SQLITE_DROP_TEMP_INDEX, sqlite3.SQLITE_DROP_TEMP_TABLE, 
            sqlite3.SQLITE_DROP_TEMP_TRIGGER, sqlite3.SQLITE_DROP_TEMP_VIEW, 
            sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_DROP_VIEW, 
            sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH
        }
        if action in forbidden_actions:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def execute(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute a parameterized SELECT query.
        """
        # Defense 4: Regex check
        if self.FORBIDDEN_KEYWORDS.search(query):
            raise ValueError(f"Prohibited SQL keyword detected in query.")
        
        # Additional safety: explicitly ensure it starts with SELECT or WITH
        query_stripped = query.strip().upper()
        if not (query_stripped.startswith("SELECT") or query_stripped.startswith("WITH") or query_stripped.startswith("PRAGMA")):
            raise ValueError("Only SELECT or WITH queries are allowed.")

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]
        
    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
