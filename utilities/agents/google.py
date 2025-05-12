import requests


class CustomGoogleAgentClient:
    def __init__(self, url: str, app_name: str, user_id: str, session_id: str):
        self.url = url
        self.app_name = app_name
        self.user_id = user_id
        self.session_id = session_id

    def warm_up(self):
        # Create session if it doesn't exist
        requests.post(self.url, headers={"Content-Type": "application/json"})

        # Call the agent
        response = requests.post(
            "http://0.0.0.0:8000/run",
            headers={"Content-Type": "application/json"},
            json={
                "app_name": self.app_name,
                "user_id": self.user_id,
                "session_id": self.session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": "Boa tarde!"}],
                },
            },
        )

        print(response.json())

    def call(self, prompt: str):
        # Create session if it doesn't exist
        requests.post(self.url, headers={"Content-Type": "application/json"})

        # Call the agent
        response = requests.post(
            "http://0.0.0.0:8000/run",
            headers={"Content-Type": "application/json"},
            json={
                "app_name": self.app_name,
                "user_id": self.user_id,
                "session_id": self.session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": prompt}],
                },
            },
        )

        return response
