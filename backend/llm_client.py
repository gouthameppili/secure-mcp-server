import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
    print("Error: GEMINI_API_KEY is not set or contains the default placeholder.")
    print("Please set your real GEMINI_API_KEY inside the 'backend/.env' file.")
    exit(1)

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Define the query function that will act as a Tool for the model
def query_enterprise_support_tickets(query: str = None) -> str:
    """
    Queries the enterprise support tickets database for tickets matching the search query.
    Use this tool if the user asks for enterprise support tickets, system issues, 
    errors, high severity events, or general database ticket status.

    Args:
        query: Optional string search query to match on title or description of tickets.
    """
    print(f"\n[MCP INTERCEPT] Intercepted tool call: query_enterprise_support_tickets(query={repr(query)})")
    try:
        # 1. Fetch valid Bearer token from local public auth route
        print("[MCP INTERCEPT] Fetching valid Bearer JWT token from http://localhost:8000/api/token...")
        token_res = requests.get("http://localhost:8000/api/token")
        token_res.raise_for_status()
        token = token_res.json()["token"]

        # 2. Call the protected /mcp/tools/query endpoint on localhost:8000
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        body = {}
        if query:
            body["query"] = query

        print("[MCP INTERCEPT] Sending authorized POST request to http://localhost:8000/mcp/tools/query...")
        api_res = requests.post("http://localhost:8000/mcp/tools/query", json=body, headers=headers)
        api_res.raise_for_status()

        results = api_res.json()
        print(f"[MCP INTERCEPT] Received {len(results)} tickets from database. Feeding data back to Gemini...")
        return json.dumps(results)
    except Exception as e:
        err_msg = f"Failed to execute local MCP tool query: {e}"
        print(f"[MCP INTERCEPT] Error: {err_msg}")
        return json.dumps({"error": err_msg})

# Initialize Gemini 2.5 Flash model with our tool
print("Initializing Gemini 2.5 Flash with enterprise search tools...")
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    tools=[query_enterprise_support_tickets]
)

# Start an interactive chat session with automatic function calling enabled
chat = model.start_chat(enable_automatic_function_calling=True)

print("\n=========================================================")
print("  Secure MCP Host Client - Interactive Terminal Console")
print("=========================================================")
print("Type your questions below (e.g. 'Show me critical tickets' or 'Is there any issue with auth?')")
print("Type 'exit' or 'quit' to exit.\n")

while True:
    try:
        user_input = input("User: ")
        if user_input.strip().lower() in ["exit", "quit"]:
            print("Exiting...")
            break
        if not user_input.strip():
            continue

        print("\nThinking...")
        response = chat.send_message(user_input)
        print(f"\nGemini: {response.text}\n")
        print("---------------------------------------------------------")
    except KeyboardInterrupt:
        print("\nExiting...")
        break
    except Exception as e:
        print(f"\nAn error occurred: {e}\n")
