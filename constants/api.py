# Agents session
GOOGLE_AGENTS_ADK_URL = "http://0.0.0.0:8000"
USER_ID = "bellanda"
SESSION_ID = "main_session"
AGENTS = ["database_query_agent", "generate_charts_agent"]
AGENTS_MAPPINGS = {}

for agent in AGENTS:
    AGENTS_MAPPINGS[agent] = {
        "url": f"{GOOGLE_AGENTS_ADK_URL}/apps/{agent}/users/{USER_ID}/sessions/{SESSION_ID}",
        "app_name": agent,
        "user_id": USER_ID,
        "session_id": SESSION_ID,
    }
