from google.generativeai import GenerativeModel
import google.generativeai as genai
import random
import os
from time import time, sleep
from dotenv import load_dotenv
import json
from proxy_rotation_v2 import build_reddit_client
import logging

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
logger = logging.getLogger('prawcore')
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GEMINI_KEY")
USERNAME = os.getenv('PROXY_USERNAME')
PASSWORD = os.getenv('PROXY_PASSWORD')
PROXIES = [f"http://{USERNAME}:{PASSWORD}@{p}" for p in os.getenv('PROXIES', "").split(',')]

# Configure Gemini key
genai.configure(api_key=API_KEY)

# Parameters
MODEL_NAME = "gemini-1.5-pro"
NUM_AGENTS = 1
POST_LIMIT = 1
AGENTS = []

# Subreddits and keywords
SUBREDDITS = ["QualityAssurance", "softwaretesting", "devops", "TechStartups", "softwaredevelopment", "software", "SoftwareTestingViews", "softwaretestingtalks", "SoftwareEngineering", "softwareengineer"]
KEYWORDS = ["black box testing tools", "test automation for startups", "QA", "test without writing code", "black box testing", "no scripting", "code testing", "unit testing"]

# Comment log file
COMMENT_LOG_FILE = "./sales-agents/resources/logging/comments.json"

# Load knowledge base
KNOWLEDGE_BASE_PATH = "C:\Users\rohir\OneDrive\Desktop\Code learning\VSC\Reddit agent"
if os.path.exists(KNOWLEDGE_BASE_PATH):
    with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
        KNOWLEDGE_BASE = f.read()
else:
    KNOWLEDGE_BASE = ""

# Load agents
def load_agents():
    AGENTS.clear()
    AGENT_CLIENT_ID = os.getenv('AGENT_CLIENT_ID', '').split(',')
    AGENT_CLIENT_SECRET = os.getenv('AGENT_CLIENT_SECRET', '').split(',')
    AGENT_USERNAME = os.getenv('AGENT_USERNAME', '').split(',')
    AGENT_PASSWORD = os.getenv('AGENT_PASSWORD', '').split(',')
    for i in range(NUM_AGENTS):
        agent = {
            "name": f"agent{i}",
            "client_id": AGENT_CLIENT_ID[i],
            "client_secret": AGENT_CLIENT_SECRET[i],
            "username": AGENT_USERNAME[i],
            "password": AGENT_PASSWORD[i],
            "proxy": PROXIES[i]
        }
        AGENTS.append(agent)

# Read comment log
def read_comment_log():
    if not os.path.exists(COMMENT_LOG_FILE):
        return {}
    with open(COMMENT_LOG_FILE, "r") as f:
        return dict(json.load(f))

# Write comment log
def write_comment_log(comment_dict):
    with open(COMMENT_LOG_FILE, "w") as f:
        json.dump(comment_dict, f, indent=2)

# Get all comments
def get_all_comments_flat(submission):
    submission.comment_sort = 'top'
    submission.comments.replace_more(limit=0)
    return list(submission.comments.list())

# Valid comment filter
def is_valid_comment(comment):
    return (
        comment.body not in ["[removed]", "[deleted]"]
        and comment.author is not None
        and comment.body.strip() != ""
    )

# Use gemini to construct a helpful Reddit comment
def construct_comment(title, content):
    model = GenerativeModel(MODEL_NAME)
    prompt = (
        "You're a Reddit user experienced in QA or dev work. "
        "You also have access to this internal QA knowledge base:\n\n"
        f"{KNOWLEDGE_BASE}\n\n"
        "Use this information (if relevant) to help construct a Reddit reply to the post below. "
        "Be friendly, natural, and helpful. You can share personal experience, tools, or tips casually. "
        "Keep the comment 3 to 6 sentences long.\n\n"
        f"Post Title: {title}\n\n"
        f"Post Content: {content}\n\n"
        "Comment:"
    )
    try:
        response = model.generate_content([prompt])
        return response.text.strip()
    except Exception as e:
        print(f"Error constructing comment for post '{title}': {e}")
        return None

# Proxy check
def is_proxy_applied(session):
    try:
        current_ip = session.get("https://api.ipify.org?format=json", timeout=5).json().get('ip')
        proxy_ips = [proxy.split('@')[-1].split(':')[0] for proxy in session.proxies.values()]
        return current_ip in proxy_ips
    except Exception as e:
        print(f"Error checking proxy: {e}")
        return False

# Sleep
def safe_sleep(seconds, jitter=0.3):
    sleep(seconds + random.uniform(0, jitter))

# Post age check
def is_recent_post(post, max_age_days=7):
    max_age_seconds = max_age_days * 86400
    post_age = time() - post.created_utc
    return post_age <= max_age_seconds

# Upvote
def upvote_with_sleep(comment):
    comment.upvote()
    safe_sleep(1)

# Bot runner
def run_bot(agent, subreddits, keywords, post_limit=3):
    reddit = build_reddit_client(agent)
    session = reddit._core._requestor._http
    if not is_proxy_applied(session):
        print("<.. Proxy is not properly configured! ..>")
        return

    comment_log = read_comment_log()
    agent_name = agent["name"]
    print(f"\nRunning agent: {agent_name} on proxy: {agent['proxy']}")

    try:
        post_count = 0
        for subreddit_name in subreddits[:1]:
            if post_count >= POST_LIMIT:
                break
            subreddit = reddit.subreddit(subreddit_name)
            safe_sleep(5, 1)
            for keyword in keywords:
                safe_sleep(1)
                for post in subreddit.search(keyword, limit=post_limit):
                    if not is_recent_post(post, 120):
                        continue
                    safe_sleep(1)
                    post_id = post.id
                    if post_id in comment_log and any(c["agent"] == agent_name for c in comment_log[post_id]):
                        continue

                    submission = reddit.submission(id=post_id)
                    all_comments = get_all_comments_flat(submission)
                    top_comments = sorted([c for c in all_comments if is_valid_comment(c)], key=lambda c: c.score, reverse=True)[:3]
                    for comment in top_comments:
                        upvote_with_sleep(comment)

                    comment = construct_comment(post.title, post.selftext)
                    if comment:
                        if post_id not in comment_log:
                            comment_log[post_id] = []
                        new_comment = post.reply(comment)
                        link = new_comment.permalink
                        comment_log[post_id].append({
                            "comment": comment,
                            "agent": agent_name,
                            "timestamp": time()
                        })
                        write_comment_log(comment_log)
                        post_count += 1
                        safe_sleep(5, 1)
    except Exception as e:
        print(f" Error searching [{subreddit_name}] with keyword [{keyword}]: {e}")

# Main runner
def run_bot_main():
    for agent in AGENTS:
        try:
            run_bot(agent, SUBREDDITS, KEYWORDS, post_limit=1)
        except Exception as e:
            print(f" Agent {agent['name']} failed: {e}")

# Load agents and run
load_agents()
run_bot_main()
