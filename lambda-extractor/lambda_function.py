# lambda_function.py
import os
import json
from datetime import datetime, timezone
import logging
import praw
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET", "reddit-ml-vikas")
SUBREDDITS = os.environ.get("SUBREDDITS", "artificial,ChatGPT,ArtificialInteligence,technology").split(",")
POST_LIMIT = int(os.environ.get("POST_LIMIT", "10"))
S3_PREFIX = os.environ.get("S3_PREFIX", "raw_data/to_process/")

s3 = boto3.client("s3", region_name="us-east-1")

def fetch_posts_from_subreddit(reddit, name, limit):
    posts = []
    subreddit = reddit.subreddit(name)
    for post in subreddit.hot(limit=limit):
        created_time = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
        created_at = created_time.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Required-field validation
        required_fields = ["id", "title", "author", "score"]
        raw = vars(post)
        missing_fields = [f for f in required_fields if raw.get(f) is None]
        if missing_fields:
            continue
        
        # Null / empty value handling
        if not post.title or post.title.strip()=="":
            continue
        safe_author=str(post.author) if post.author else "unknown_author"

        clean_post = {
            "subreddit": name,
            "id": str(post.id),
            "title": post.title.strip(),
            "author": safe_author,
            "score": int(post.score),
            "num_comments": int(post.num_comments),
            "created_at": created_at,
            "url": post.url,
            "permalink": f"https://www.reddit.com{post.permalink}",
        }

        clean_post["validation_status"] = "passed"
    
    posts.append(clean_post)

    return posts

def lambda_handler(event, context):
    # Read Reddit credentials
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "reddit-sentiment-pipeline:v1.0 (by u/gnan_vikas)")

    if not (client_id and client_secret):
        logger.error("Missing Reddit credentials in environment variables.")
        raise Exception("Reddit credentials not set")

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        check_for_async=False
    )

    all_posts = []
    for name in SUBREDDITS:
        try:
            logger.info(f"Fetching {POST_LIMIT} posts from r/{name}")
            all_posts.extend(fetch_posts_from_subreddit(reddit, name.strip(), POST_LIMIT))
        except Exception as e:
            logger.exception(f"Error fetching from r/{name}: {e}")

    # Remove duplicates by Reddit post ID
    unique_posts = {post["id"]: post for post in all_posts}
    deduped_posts = list(unique_posts.values())
    logger.info(f"Removed {len(all_posts) - len(deduped_posts)} duplicate posts")

    file_name = "reddit_raw_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".json"
    s3_key = S3_PREFIX + file_name

    # Upload JSON to S3
    body = json.dumps(deduped_posts)
    s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=body.encode("utf-8"))

    logger.info(f"Uploaded {len(deduped_posts)} unique posts to s3://{S3_BUCKET}/{s3_key}")
    return {
        "statusCode": 200,
        "message": "success",
        "count": len(deduped_posts),
        "s3_key": s3_key
    }

