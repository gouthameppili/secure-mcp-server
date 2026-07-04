import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import json
from bson import json_util

load_dotenv()
uri = os.getenv('MONGODB_URI')

async def main():
    client = AsyncIOMotorClient(uri)
    try:
        db = client.get_default_database()
    except Exception:
        db = client["secure_mcp"]
        
    logs = db.logs
    count = await logs.count_documents({})
    print(f"Total logs in database: {count}")
    
    print("Latest 3 logs:")
    async for log in logs.find().sort("_id", -1).limit(3):
        # Convert ObjectId to string for printing
        print(json.dumps(log, default=json_util.default, indent=2))

asyncio.run(main())
