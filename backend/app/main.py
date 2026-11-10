from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analyze import router as analyze_router

app = FastAPI(title="ConstantaE API", version="0.1.0")

# The extension calls the API from its background worker, whose origin is
# chrome-extension://<id> or moz-extension://<id>.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome|moz)-extension://.*$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(analyze_router)
