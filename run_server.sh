#!/bin/bash
# Run the FastAPI server with uvicorn
uvicorn fastapi_server:app --host 0.0.0.0 --port 8080 --reload

