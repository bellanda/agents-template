import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent))

import time

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

import constants.api
from utilities.agents.google import CustomGoogleAgentClient

BASE_DIR = pathlib.Path(__file__).parent.parent

# FastAPI app
app = FastAPI()

# Agents clients
database_query_agent_client = CustomGoogleAgentClient(**constants.api.AGENTS_MAPPINGS["database_query_agent"])
generate_charts_agent_client = CustomGoogleAgentClient(**constants.api.AGENTS_MAPPINGS["generate_charts_agent"])


# Endpoints
@app.get("/download_file")
async def download_file(file_name: str):
    file_path = BASE_DIR / "data" / "server" / file_name
    return FileResponse(path=file_path, filename=file_path.name)


@app.get("/database_query_agent")
def database_query_agent_endpoint(instructions: str) -> dict:
    start_time = time.perf_counter()
    response = database_query_agent_client.call(instructions)
    result = response.json()
    print(f"Time taken: {time.perf_counter() - start_time} seconds")
    return JSONResponse(result)


@app.get("/generate_charts_agent")
def generate_charts_agent_endpoint(instructions: str) -> dict:
    start_time = time.perf_counter()
    response = generate_charts_agent_client.call(instructions)
    result = response.json()
    print(f"Time taken: {time.perf_counter() - start_time} seconds")
    return JSONResponse(result)


# Run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8005)
