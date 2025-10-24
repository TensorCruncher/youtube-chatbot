import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from typing import Dict, Any
from threading import Lock
from collections import defaultdict

from rag_pipeline import (
    ingest,
    get_from_ram,
    ask_llm,
    llm,
    parser,
    prompt
)

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None)


limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://pjolcmgepmllfkicompfklfhdobbmiab"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_loaded_indexes = {}

STORE_DIR = os.environ.get("STORE_DIR", "./store")
os.makedirs(STORE_DIR, exist_ok=True)

_loaded_indexes: Dict[str, Any] = {}
_locks: Dict[str, Lock] = defaultdict(Lock)

class AskBody(BaseModel):
    question: str

@app.post("/ask")
@limiter.limit("100/hour")
def ask(request: Request, video_id: str, body: AskBody):
    ingest_transcript = ingest(video_id, _loaded_indexes, _locks, STORE_DIR)
    
    question = body.question
    retriever = get_from_ram(video_id, _loaded_indexes)
    result = ask_llm(retriever, llm, parser, prompt, question, video_id)

    return {"answer": result, "ingest": ingest_transcript["source"], "video_id": video_id}