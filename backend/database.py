import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

# We start with the pool set to None when the server boots
pool = None

async def get_pool():
    """
    Creates the database connection pool if it doesn't exist yet, 
    and returns the active pool.
    """
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    return pool

async def close_pool():
    """
    Closes all active database connections in the pool when 
    the backend server shuts down.
    """
    global pool
    if pool:
        await pool.close()
        pool = None
