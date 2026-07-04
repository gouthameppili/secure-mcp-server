import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

# We will initialize these globally in init_db
client: AsyncIOMotorClient = None
db = None

logger = logging.getLogger(__name__)

async def init_db():
    """
    Initializes the MongoDB client, checks the connection,
    and seeds the database with mock tickets if empty.
    """
    global client, db
    
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI environment variable is not set")
        
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URI)
    
    # Verify the connection by pinging the admin database
    try:
        await client.admin.command("ping")
        logger.info("Successfully connected to MongoDB (ping successful).")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise RuntimeError(f"Database connection failed: {e}") from e
        
    # Get the default database from URI, or fall back to 'secure_mcp'
    try:
        db = client.get_default_database()
    except Exception:
        db = client["secure_mcp"]
        
    logger.info(f"Database selected: {db.name}")
    
    # Seed the tickets collection if empty
    tickets_collection = db["tickets"]
    count = await tickets_collection.count_documents({})
    if count == 0:
        logger.info("Seeding mock enterprise support tickets...")
        mock_tickets = [
            {
                "userId": "admin_123",
                "title": "API Gateway Authentication Failure",
                "description": "Enterprise API gateway is failing to authorize requests with valid JWT tokens. Returns HTTP 401.",
                "severity": "CRITICAL",
                "status": "OPEN",
                "createdAt": "2026-06-10T23:00:00Z"
            },
            {
                "userId": "admin_123",
                "title": "High Latency in Database Queries",
                "description": "Database query response times have spiked to > 2000ms under load.",
                "severity": "HIGH",
                "status": "IN_PROGRESS",
                "createdAt": "2026-06-10T23:05:00Z"
            }
        ]
        result = await tickets_collection.insert_many(mock_tickets)
        logger.info(f"Seeded {len(result.inserted_ids)} mock tickets.")
    else:
        logger.info(f"Tickets collection already contains {count} documents. Skipping seed.")

def get_db():
    """
    Returns the active database instance.
    """
    global db
    if db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return db

async def save_execution_log(endpoint: str, user_id: str, status_code: int, status_label: str, latency_ms: int = 50, error_details: dict = None):
    """
    Saves an execution log into the 'logs' collection.
    """
    import datetime
    import random
    
    try:
        global db
        if db is None:
            try:
                db = get_db()
            except Exception:
                logger.error("Cannot save execution log: Database not initialized.")
                return
                
        logs_collection = db["logs"]
        
        # Determine sequential id
        count = await logs_collection.count_documents({})
        log_id = 1001 + count
        
        now = datetime.datetime.utcnow()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Format: YYYY-MM-DD HH:MM:SS.mmm
        
        # Build payload matching the frontend expectations
        session_token = f"tok_{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=8))}"
        
        payload = {
            "jsonrpc": "2.0",
            "id": log_id,
            "timestamp": time_str,
            "auth": {
                "userId": user_id,
                "sessionToken": session_token,
                "scope": ["tools:read", "resources:read"]
            },
            "request": {
                "method": "POST" if "query" in endpoint or "tools" in endpoint else "GET",
                "endpoint": endpoint,
                "latencyMs": latency_ms
            }
        }
        
        if status_code == 200:
            if endpoint == "/mcp/tools/list":
                data = {
                    "tools": [
                        {"name": "query_database", "inputSchema": {"type": "object"}},
                        {"name": "read_file", "inputSchema": {"type": "object"}},
                        {"name": "web_search", "inputSchema": {"type": "object"}}
                    ],
                    "nextCursor": None
                }
            elif endpoint == "/mcp/ping":
                data = {"alive": True, "uptime": 99847}
            elif endpoint == "/mcp/resources":
                data = [
                    {
                        "name": "Support Tickets",
                        "description": "Enterprise support logs containing system errors, status, and severities."
                    }
                ]
            else:
                data = {
                    "content": [{"type": "text", "text": "Tool executed successfully."}],
                    "isError": False
                }
                
            payload["result"] = {
                "status": "success",
                "data": data
            }
        else:
            errors = {
                401: {"code": -32001, "message": "Authentication required", "data": {"hint": "Provide a valid Bearer token."}},
                403: {"code": -32003, "message": "Permission denied", "data": {"hint": "Insufficient scope for this resource."}},
                429: {"code": -32029, "message": "Rate limit exceeded", "data": {"retryAfter": 30}},
                500: {"code": -32000, "message": "Internal server error", "data": {"trace": "ERR_HANDLER_PANIC at line 312"}}
            }
            if error_details:
                payload["error"] = error_details
            else:
                payload["error"] = errors.get(status_code, errors[500])
                
        log_document = {
            "id": log_id,
            "time": time_str,
            "userId": user_id,
            "endpoint": endpoint,
            "statusCode": status_code,
            "statusLabel": status_label,
            "payload": payload
        }
        
        await logs_collection.insert_one(log_document)
        logger.info(f"Execution log saved for endpoint {endpoint} with status {status_code}")
    except Exception as e:
        logger.error(f"Failed to save execution log: {e}")
