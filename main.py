from fastapi import FastAPI

from app.api.v1.api import api_router
from fastapi.staticfiles import StaticFiles


app = FastAPI(
    title="LMT API",
    version="1.0.0"
)

app.include_router(
    api_router,
    prefix="/api/v1"
)


app.mount(
    "/uploads",
    StaticFiles(directory="app/uploads"),
    name="uploads",
)