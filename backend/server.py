"""
FastAPI server with SSE streaming
Serves frontend + streams workflow events in real-time
"""
import asyncio
import json
import os
import sys
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from workflow import run_workflow_stream, run_workflow_json
from utils import get_config_version, reload_config, load_users, load_datasets
from models import WorkflowRequest

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Visa GDO Data Access Automation",
    description="Multi-agent system for data access approval with ABAC policy engine",
    version="1.0.0"
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"
assets_dir = frontend_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
async def serve_frontend():
    """Serve main frontend HTML - workflow demo with SSE integration"""
    workflow_path = frontend_dir / "workflow.html"
    if workflow_path.exists():
        return FileResponse(workflow_path)
    return {"message": "Frontend not found. Place frontend files in /frontend directory."}


@app.get("/index.html")
async def serve_index():
    """Serve legacy index.html if needed"""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "index.html not found"}


@app.get("/api/stream_workflow")
async def stream_workflow(
    request_text: str = Query(..., description="Natural language data access request"),
    requester_email: str = Query(..., description="Email of requester"),
    selected_dataset: str = Query(None, description="Pre-selected dataset (optional)")
):
    """
    SSE streaming endpoint
    Streams agent execution events in real-time
    
    Events: discovery, intake, policy, provision, notify, audit, done, error
    """
    async def event_generator():
        """Generate SSE events from workflow"""
        try:
            async for event_name, event_data in run_workflow_stream(
                request_text=request_text,
                requester_email=requester_email,
                selected_dataset=selected_dataset
            ):
                # Format as SSE event - convert dict to JSON string
                json_data = json.dumps(event_data) if isinstance(event_data, dict) else event_data
                sse_message = f"event: {event_name}\ndata: {json_data}\n\n"
                yield sse_message.encode('utf-8')
                
                # Small delay for client to process
                await asyncio.sleep(0.05)
        
        except Exception as e:
            error_event = f"event: error\ndata: {{\"error\": \"server_error\", \"message\": \"{str(e)}\"}}\n\n"
            yield error_event.encode('utf-8')
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.post("/api/run_workflow")
async def run_workflow(request: WorkflowRequest):
    """
    Non-streaming JSON endpoint
    Returns complete workflow result as single JSON object
    Useful for testing/debugging
    """
    result = await run_workflow_json(
        request_text=request.request_text,
        requester_email=request.requester_email,
        selected_dataset=request.selected_dataset
    )
    return result


@app.get("/api/config/users")
async def get_users():
    """Get all users from users.json"""
    return load_users()


@app.get("/api/config/datasets")
async def get_datasets():
    """Get all datasets from datasets.json"""
    return load_datasets()


@app.get("/api/config/version")
async def get_version():
    """Get current config version hash"""
    return {"version": get_config_version()}


@app.post("/api/config/reload")
async def reload_configs():
    """Force reload config files and return new version"""
    new_version = reload_config()
    return {
        "status": "reloaded",
        "version": new_version,
        "message": "Config files reloaded successfully"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Visa GDO Access Automation",
        "config_version": get_config_version()
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    
    print("=" * 60)
    print("🚀 Visa GDO Data Access Automation")
    print("=" * 60)
    print(f"Frontend:  http://localhost:{port}/")
    print(f"SSE API:   http://localhost:{port}/api/stream_workflow")
    print(f"JSON API:  http://localhost:{port}/api/run_workflow")
    print(f"Config:    http://localhost:{port}/api/config/version")
    print(f"Health:    http://localhost:{port}/api/health")
    print("=" * 60)
    print(f"Config version: {get_config_version()}")
    print("=" * 60)
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
