from fastapi import FastAPI
from api.verify import router
from core.registry import discover_and_sync

def lifespan(app: FastAPI):
    discover_and_sync()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(router)

@app.get("/")
def health_check():
    return {"status":"ok"}