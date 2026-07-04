import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db, save_execution_log
from app.auth import get_current_user_id, verify_access_token, create_access_token
from app.mcp import router as mcp_router
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
import json
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan context manager.
    Runs database initialization on startup and logs status.
    """
    logger.info("Starting up secure-mcp-server backend...")
    try:
        await init_db()
        logger.info("Database initialized successfully during startup.")
    except Exception as e:
        logger.critical(f"Database initialization failed on startup: {e}")
        raise e
        
    yield
    
    logger.info("Shutting down secure-mcp-server backend...")

app = FastAPI(
    title="Secure MCP Server Backend",
    description="FastAPI Backend for Secure Model Context Protocol Server",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Request logging middleware for MCP routes
@app.middleware("http")
async def log_mcp_requests(request: Request, call_next):
    # Intercept MCP routes, excluding the logs endpoint itself to avoid log loops
    if request.url.path.startswith("/mcp") and not request.url.path.endswith("/logs"):
        start_time = time.time()
        
        user_id = "anonymous"
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            try:
                token = auth_header.split(" ")[1]
                user_id = verify_access_token(token)
            except Exception:
                try:
                    import jwt
                    payload = jwt.decode(token, options={"verify_signature": False})
                    user_id = payload.get("userId", "anonymous")
                except Exception:
                    pass

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise e
        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            status_labels = {
                200: "OK",
                201: "Created",
                400: "Bad Request",
                401: "Unauthorized",
                403: "Forbidden",
                404: "Not Found",
                429: "Too Many Requests",
                500: "Internal Server Error"
            }
            status_label = status_labels.get(status_code, "Error" if status_code >= 400 else "OK")
            
            await save_execution_log(
                endpoint=request.url.path,
                user_id=user_id,
                status_code=status_code,
                status_label=status_label,
                latency_ms=latency_ms
            )
            
        return response
        
    return await call_next(request)

app.include_router(mcp_router)

@app.get("/api/token")
async def get_token():
    """
    Public endpoint to generate a valid access token for frontend dashboard calls.
    """
    token = create_access_token(user_id="usr_a3f9k1")
    return {"token": token}

@app.get("/health")
async def health_check():
    """
    Simple async GET route that returns a status confirmation.
    """
    return {
        "status": "healthy",
        "service": "secure-mcp-server-backend"
    }

@app.get("/api/test-auth")
async def test_auth(user_id: str = Depends(get_current_user_id)):
    """
    Protected dummy route that depends on get_current_user_id and returns the user ID.
    """
    return {
        "authenticated": True,
        "userId": user_id
    }

def tool_query_enterprise_support_tickets(query: str = "") -> str:
    """
    Queries the enterprise support tickets database for tickets matching the search query.
    Use this tool if the user asks for enterprise support tickets, system issues, 
    errors, high severity events, or general database ticket status.
    """
    pass

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, user_id: str = Depends(get_current_user_id)):
    from fastapi.responses import JSONResponse
    import traceback
    
    try:
        logger.info(f"Received chat message from {user_id}: {req.message}")
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            return {"response": "Error: GEMINI_API_KEY is not configured on the backend."}

        from app.database import get_db

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            tools=[tool_query_enterprise_support_tickets]
        )

        formatted_history = []
        for msg in req.history:
            role = "user" if msg.get("role") == "user" else "model"
            formatted_history.append({"role": role, "parts": [msg.get("content", "")]})

        chat = model.start_chat(history=formatted_history)
        
        response = chat.send_message(req.message)
        
        # Check if Gemini wants to call a tool
        if response.candidates and response.candidates[0].content.parts:
            part = response.candidates[0].content.parts[0]
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                if fc.name == "tool_query_enterprise_support_tickets":
                    # Convert protobuf map to dict properly
                    query_args = type(fc).to_dict(fc).get("args", {})
                    query = query_args.get("query", "")
                    
                    try:
                        db = get_db()
                        tickets_collection = db["tickets"]
                        filter_query = {"userId": user_id}
                        if query:
                            filter_query["$or"] = [
                                {"title": {"$regex": query, "$options": "i"}},
                                {"description": {"$regex": query, "$options": "i"}}
                            ]
                        
                        cursor = tickets_collection.find(filter_query)
                        tickets = []
                        async for ticket in cursor:
                            if "_id" in ticket:
                                ticket["_id"] = str(ticket["_id"])
                            tickets.append(ticket)
                        
                        tool_result_str = json.dumps(tickets)
                        
                        await save_execution_log(
                            endpoint="/mcp/tools/query_enterprise_support_tickets",
                            user_id=user_id,
                            status_code=200,
                            status_label="OK",
                            latency_ms=15
                        )
                        
                    except Exception as e:
                        tool_result_str = json.dumps({"error": str(e)})
                        await save_execution_log(
                            endpoint="/mcp/tools/query_enterprise_support_tickets",
                            user_id=user_id,
                            status_code=500,
                            status_label="Error",
                            latency_ms=10
                        )

                    response = chat.send_message(
                        {
                            "function_response": {
                                "name": "tool_query_enterprise_support_tickets",
                                "response": {"result": tool_result_str}
                            }
                        }
                    )

        return {"response": response.text}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"response": f"Backend Error: {str(e)}"})

