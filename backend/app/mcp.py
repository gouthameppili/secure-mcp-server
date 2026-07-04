import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.auth import get_current_user_id
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp")

class QueryRequest(BaseModel):
    query: Optional[str] = None

@router.get("/resources")
async def get_resources(user_id: str = Depends(get_current_user_id)):
    """
    Protected route that returns a JSON list describing the available resource collections.
    """
    return [
        {
            "name": "Support Tickets",
            "description": "Enterprise support logs containing system errors, status, and severities."
        }
    ]

@router.post("/tools/query")
async def query_tools(req: QueryRequest, user_id: str = Depends(get_current_user_id)):
    """
    Protected route that accepts a JSON body containing a query.
    Queries the 'tickets' collection asynchronously using Motor,
    filters strictly by the authenticated 'userId', and streams results back.
    """
    try:
        db = get_db()
    except RuntimeError as e:
        logger.error(f"Database not initialized: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection is not initialized."
        )

    # Construct the query filter
    filter_query = {"userId": user_id}
    if req.query:
        # Match case-insensitively on title or description
        filter_query["$or"] = [
            {"title": {"$regex": req.query, "$options": "i"}},
            {"description": {"$regex": req.query, "$options": "i"}}
        ]

    tickets_collection = db["tickets"]
    cursor = tickets_collection.find(filter_query)

    async def ticket_streamer():
        yield "["
        is_first = True
        try:
            async for ticket in cursor:
                # Convert MongoDB ObjectId to string for JSON serialization
                if "_id" in ticket:
                    ticket["_id"] = str(ticket["_id"])
                
                chunk = json.dumps(ticket)
                if not is_first:
                    yield "," + chunk
                else:
                    yield chunk
                    is_first = False
        except Exception as e:
            logger.error(f"Error while streaming database query results: {e}")
        finally:
            yield "]"

    return StreamingResponse(ticket_streamer(), media_type="application/json")

@router.get("/logs")
async def get_logs(user_id: str = Depends(get_current_user_id)):
    """
    Protected route that returns the 20 most recent log documents, sorted by time descending.
    """
    try:
        db = get_db()
    except RuntimeError as e:
        logger.error(f"Database not initialized: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection is not initialized."
        )

    logs_collection = db["logs"]
    cursor = logs_collection.find({}, {"_id": 0}).sort("time", -1).limit(20)
    
    logs = []
    async for doc in cursor:
        logs.append(doc)
        
    return logs
