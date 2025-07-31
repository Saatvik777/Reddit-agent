import requests
import praw
import os
from dotenv import load_dotenv
import time
load_dotenv()

NAME = 'testing api'
USERNAME = os.getenv('PROXY_USERNAME')
PASSWORD = os.getenv('PROXY_PASSWORD')
PROXIES = [f"http://{USERNAME}:{PASSWORD}@{p}" for p in os.getenv('PROXIES', "").split(',')]

class RateLimitedSession(requests.Session):
    def __init__(self, threshold=50):
        super().__init__()
        self.threshold = threshold
        self.remaining = None
        self.reset = None
        self.used = 0  # total used in this window

    def send(self, request, **kwargs):
        response = super().send(request, **kwargs)
        headers = response.headers

        remaining = headers.get("x-ratelimit-remaining")
        reset = headers.get("x-ratelimit-reset")
        used = headers.get("x-ratelimit-used")

        if used is not None:
            self.used = float(used)

        if remaining is not None:
            self.remaining = float(remaining)
            self.reset = float(reset or 0)
            print(f"📊 Rate Limit | Used: {self.used} | Remaining: {self.remaining} | Reset in: {self.reset:.0f}s")
            with open("./sales-agents/resources/rate_limit_log.txt", "a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | Used: {self.used} | Remaining: {self.remaining} | Reset in: {self.reset:.0f}s\n")


            if self.remaining < self.threshold:
                sleep_time = self.reset + 5
                print(f"⏳ Sleeping for {sleep_time:.0f} seconds to respect rate limit...")
                time.sleep(sleep_time)

        return response



def build_reddit_client(agent):
    # Create and configure a session with proxy
    session = RateLimitedSession()
    session.proxies = {
    "http": agent["proxy"],
    "https": agent["proxy"]
    }
    session.verify = True

    # Build and return the Reddit client
    reddit = praw.Reddit(
        client_id=agent["client_id"],
        client_secret=agent["client_secret"],
        username=agent["username"],
        password=agent["password"],
        user_agent= f"testscript by /u/{agent['username']}",
        requestor_kwargs={"session": session, "timeout": 10}  # ✅ only pass session + timeout
    )

    return reddit