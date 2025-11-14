from fastapi import FastAPI
from .api import router as api_router
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="RAG FastAPI SQLite FTS with Groq" )
app.include_router(api_router, prefix="/api")

origins = os.environ.get('CORS_ORIGINS', '*',"https://superllm.vercel.app")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origins] if origins != '*' else ['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/')
def root():
    return {"status": "ok"}
