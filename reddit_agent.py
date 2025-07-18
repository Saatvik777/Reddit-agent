import openai
from openai import OpenAI
import praw
import os
from dotenv import load_dotenv
import json
import time
import random

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



# List of subreddits and keywords to search
SUBREDDITS = ["QualityAssurance", "softwaretesting", "devops", "TechStartups"]
KEYWORDS = ["black box testing tools", "test automation for startups", "QA", "test without writing code", "black box testing", "no scripting"]

# Log file to prevent duplicate replies across agents
LOG_FILE = "replied_posts.json"

# Multiple Reddit agents
AGENTS = [
    {
        "name": "agent1",
        "client_id": os.getenv("AGENT1_CLIENT_ID"),
        "client_secret": os.getenv("AGENT1_CLIENT_SECRET"),
        "username": os.getenv("AGENT1_USERNAME"),
        "password": os.getenv("AGENT1_PASSWORD")
    }#,
#    {
#        "name": "agent2",
#        "client_id": os.getenv("AGENT2_CLIENT_ID"),
#        "client_secret": os.getenv("AGENT2_CLIENT_SECRET"),
#        "username": os.getenv("AGENT2_USERNAME"),
#        "password": os.getenv("AGENT2_PASSWORD")
#    }
]


# Load or create reply log
def load_log():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r") as f:
        return set(json.load(f))

def save_log(log_set):
    with open(LOG_FILE, "w") as f:
        json.dump(list(log_set), f)

# Create Reddit instance per agent
def create_reddit_instance(agent):
    return praw.Reddit(
        client_id=agent["client_id"],
        client_secret=agent["client_secret"],
        username=agent["username"],
        password=agent["password"],
        user_agent=f"Reddit AI Agent ({agent['name']})"
    )

# Use OpenAI to construct a helpful Reddit comment
def construct_comment(title, content):
    prompt = f"Write a helpful and engaging Reddit comment for the following post:\n\nTitle: {title}\n\nContent: {content}\n\nComment:"
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f" OpenAI error: {e}")
        return None

# Bot logic for one agent
def run_bot(agent, subreddits, keywords, post_limit=3):
    reddit = create_reddit_instance(agent)
    agent_name = agent["name"]
    log = load_log()

    print(f"\n Running agent: {agent_name}")

    for subreddit_name in subreddits:
        subreddit = reddit.subreddit(subreddit_name)
        print(f" [{agent_name}] Searching r/{subreddit_name}")

        for keyword in keywords:
            print(f"    Keyword: {keyword}")
            try:
                for post in subreddit.search(keyword, limit=post_limit):
                    if post.id in log:
                        continue

                    print(f"\n [{agent_name}] Found post:")
                    print(f"   Title: {post.title}")
                    print(f"   Content: {post.selftext}")

                    comment = construct_comment(post.title, post.selftext)
                    if comment:
                        print(f" Generated Comment:\n{comment}\n")
                        log.add(post.id)
                        save_log(log)
                        time.sleep(5)
                        #  Commented out Reddit post reply:
                        # post.reply(comment)
            except Exception as e:
                print(f" Error searching [{subreddit_name}] with keyword [{keyword}]: {e}")

if __name__ == "__main__":
    for agent in AGENTS:
        run_bot(agent, SUBREDDITS, KEYWORDS, post_limit=3)
        print(f" Finished round for: {agent['name']}")
        time.sleep(random.randrange(3600,7200)) 

