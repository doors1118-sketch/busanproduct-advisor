import os
from app.api_server import app
from fastapi import Request

@app.post("/_test_set_env")
async def test_set_env(request: Request):
    data = await request.json()
    for k, v in data.items():
        os.environ[k] = str(v)
    return {"status": "ok"}
