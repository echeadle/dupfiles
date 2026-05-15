from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.db import get_connection, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_connection()
    init_db(conn)
    conn.close()
    yield


app = FastAPI(title="Duplicate File Finder", version="1.0.0", lifespan=lifespan)
app.include_router(router)
