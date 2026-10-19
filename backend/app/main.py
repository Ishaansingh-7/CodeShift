import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from codeshift import __version__
from .routes import router
from .runner import warm


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(title="CodeShift", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
