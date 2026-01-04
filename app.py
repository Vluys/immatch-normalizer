from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Payload(BaseModel):
    raw: dict

@app.post("/normalize")
def normalize(payload: Payload):
    return {
        "status": "ok",
        "received": payload.raw
    }
