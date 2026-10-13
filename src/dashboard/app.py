import os
import shutil
import tempfile
import asyncio
from typing import List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel

from src.parser import parse_and_validate_tax_data
from src.iris_driver import run_iris_posting

app = FastAPI(title="FBR IRIS 2.0 Auto-Posting Agent", version="1.0.0")

current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
templates_dir = os.path.join(current_dir, "templates")

os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()
active_task = None

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    index_file = os.path.join(templates_dir, "index.html")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(
            content=f.read(),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

@app.post("/api/parse-excel")
async def parse_excel_endpoint(file: UploadFile = File(...), tax_year: int = Form(2026)):
    temp_path = None
    try:
        suffix = os.path.splitext(file.filename)[1] or ".xls"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name

        data = parse_and_validate_tax_data(temp_path, tax_year=tax_year)
        return {"status": "success", "filename": file.filename, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@app.post("/api/start-posting")
async def start_posting_endpoint(request: Request):
    global active_task
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
    
    cnic = str(payload.get("cnic", "")).strip()
    password = str(payload.get("password", "")).strip()
    tax_year = int(payload.get("tax_year", 2026))
    headless = bool(payload.get("headless", False))
    
    if not cnic or not password:
        raise HTTPException(status_code=400, detail="CNIC and Password are required.")

    # Determine tax data
    tax_data = payload.get("parsed_data")
    if not tax_data:
        raise HTTPException(
            status_code=400,
            detail="No tax computation data provided. Please upload the client's Excel workbook before executing."
        )

    async def status_callback(event: Dict[str, Any]):
        await manager.broadcast(event)

    async def worker():
        try:
            await manager.broadcast({
                "step": "INIT",
                "message": f"Starting automated session for CNIC: {cnic} (Draft Mode)...",
                "screenshot": None
            })
            result = await run_iris_posting(
                credentials={"cnic": cnic, "password": password},
                tax_data=tax_data,
                status_callback=status_callback,
                headless=headless
            )
            await manager.broadcast({
                "step": "SUCCESS",
                "message": f"Complete! Return saved to Drafts. Audit log: {result['audit_path']}",
                "screenshot": None
            })
        except asyncio.CancelledError:
            await manager.broadcast({
                "step": "ABORTED",
                "message": "Session stopped by user. Browser closed.",
                "screenshot": None
            })
        except Exception as err:
            await manager.broadcast({
                "step": "ERROR",
                "message": f"Automation Error: {str(err)}",
                "screenshot": None
            })
        finally:
            active_task = None

    active_task = asyncio.create_task(worker())
    return {"status": "started", "message": "Automation worker launched."}

@app.post("/api/stop-posting")
async def stop_posting_endpoint():
    global active_task
    if active_task and not active_task.done():
        active_task.cancel()
        active_task = None
        return {"status": "stopped", "message": "Automation stopped successfully."}
    return {"status": "idle", "message": "No active automation task was running."}

@app.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep-alive receive ping
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
