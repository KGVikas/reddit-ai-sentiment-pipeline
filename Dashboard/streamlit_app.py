import streamlit as st
import boto3
import pandas as pd
from io import StringIO
from sklearn.feature_extraction.text import TfidfVectorizer
import ast

# ---------- AWS Setup ----------
S3_BUCKET = "reddit-ml-vikas"
REGION = "us-east-1"

s3 = boto3.client("s3", region_name=REGION)

# ---------- Helper Function ----------
def get_latest_csv_from_s3():
    """Fetch the latest processed CSV file from S3."""
    response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="csv_data/")
    files = [obj["Key"] for obj in response.get("Contents", []) if obj["Key"].endswith(".csv")]

    if not files:
        st.error("No processed CSV files found in S3.")
        st.stop()

    latest_file = sorted(files)[-1]
    st.info(f"📁 Using file: {latest_file}")

    obj = s3.get_object(Bucket=S3_BUCKET, Key=latest_file)
    csv_data = obj["Body"].read().decode("utf-8")

    return pd.read_csv(StringIO(csv_data))

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Reddit AI Sentiment Dashboard", layout="wide")

st.title("📊 Reddit AI Sentiment Analysis Dashboard")
st.caption("Automated pipeline using AWS Lambda, S3, and Comprehend — visualized via Streamlit")

df = get_latest_csv_from_s3()

# Make common column name fallbacks so later code that expects Title/Author/URL/Subreddit works
if "Author" not in df.columns and "author" in df.columns:
    df["Author"] = df["author"]
if "Title" not in df.columns and "title" in df.columns:
    df["Title"] = df["title"]
if "URL" not in df.columns and "url" in df.columns:
    df["URL"] = df["url"]
if "Subreddit" not in df.columns and "subreddit" in df.columns:
    df["Subreddit"] = df["subreddit"]

# Ensure a Sentiment column exists 
def derive_label_from_score(x):
    try:
        d = ast.literal_eval(x) if isinstance(x, str) else {}
        if not d:
            return "NEUTRAL"
        return "POSITIVE" if d.get("Positive", 0) >= d.get("Negative", 0) else "NEGATIVE"
    except Exception:
        return "NEUTRAL"

if "Sentiment" not in df.columns:
    if "SentimentScore" in df.columns:
        df["Sentiment"] = df["SentimentScore"].apply(derive_label_from_score)
    else:
        df["Sentiment"] = "NEUTRAL"

# ---------- Overview ----------
st.subheader("Dataset Overview")
st.write(df.head())

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Posts", len(df))
col2.metric("Positive Posts", int((df["Sentiment"] == "POSITIVE").sum()))
col3.metric("Negative Posts", int((df["Sentiment"] == "NEGATIVE").sum()))
col4.metric("Neutral Posts", int((df["Sentiment"] == "NEUTRAL").sum()))


# ---------- Top Authors by Sentiment ----------
st.subheader("🏆 Top Authors by Average Sentiment Score")

# ---------- SentimentScore parsing ----------
def parse_score(x):
    try:
        d = ast.literal_eval(x) if isinstance(x, str) else {}
        return {"Positive": float(d.get("Positive", 0)), "Negative": float(d.get("Negative", 0))}
    except Exception:
        return {"Positive": 0.0, "Negative": 0.0}

if "SentimentScore" in df.columns:
    scores = df["SentimentScore"].apply(parse_score)
    df["Positive"] = scores.apply(lambda d: d["Positive"])
    df["Negative"] = scores.apply(lambda d: d["Negative"])
    df["NetSentiment"] = df["Positive"] - df["Negative"]
else:
    df["Positive"] = 0.0
    df["Negative"] = 0.0
    df["NetSentiment"] = 0.0

author_sentiment = (
    df.groupby("Author")["NetSentiment"]
    .mean()
    .sort_values(ascending=False)
    .head(10)
)

st.bar_chart(author_sentiment)


# ---------- Sentiment Distribution ----------
st.subheader("📊 Sentiment Distribution")
sentiment_counts = df['Sentiment'].value_counts()
st.bar_chart(sentiment_counts)

# ---------- Clickable Links ----------
def make_clickable(url):
    return f'<a href="{url}" target="_blank">🔗 Open Post</a>'

df["Post Link"] = df["URL"].apply(make_clickable)

# ---------- Interactive Filter ----------
st.subheader("🎯 Filter by Subreddit")
subreddits = st.multiselect("Select Subreddits", df["Subreddit"].unique(), default=df["Subreddit"].unique())
filtered_df = df[df["Subreddit"].isin(subreddits)]

# ---------- Limit Display ----------
max_rows = st.slider("Number of posts to display", min_value=5, max_value=50, value=10, step=5)
limited_df = filtered_df.head(max_rows)

# ---------- Clean Table Styling ----------
st.markdown("""
    <style>
        table {
            width: 100%;
        }
        th {
            text-align: center !important;
            vertical-align: middle !important;
            white-space: nowrap !important;
        }
        td:nth-child(1) {
            text-align: left !important;
            width: 55%;
            word-wrap: break-word;
        }
        td:nth-child(2), td:nth-child(3) {
            text-align: center !important;
            vertical-align: middle !important;
        }
        td:nth-child(4) {
            text-align: center !important;
            white-space: nowrap !important;
        }
        /* 🔗 Link styling: light blue -> darker when clicked */
        a {
            text-decoration: none !important;
            color: #4a90e2 !important;
            font-weight: 600;
        }
        a:visited {
            color: #0f4c81 !important;
        }
        a:hover {
            color: #1b75bb !important;
        }
    </style>
""", unsafe_allow_html=True)

st.write(
    limited_df[["Title", "Subreddit", "Sentiment", "Post Link"]]
    .to_html(escape=False, index=False),
    unsafe_allow_html=True
)

st.subheader("💬 Distinctive Keywords in Positive Posts")

positive_titles = df[df["Sentiment"] == "POSITIVE"].get("Title", pd.Series(dtype=str)).dropna().tolist()

if positive_titles:
    vectorizer = TfidfVectorizer(stop_words="english", max_features=15)
    tfidf_matrix = vectorizer.fit_transform(positive_titles)
    feature_names = vectorizer.get_feature_names_out()
    scores = tfidf_matrix.sum(axis=0).A1
    keywords_df = pd.DataFrame({"Keyword": feature_names, "Importance": scores}).sort_values("Importance", ascending=False)
    st.bar_chart(keywords_df.set_index("Keyword"))
else:
    st.info("No positive posts found to extract keywords.")


# ---------- Trend Analysis ----------
st.subheader("📈 Sentiment by Subreddit")
trend = df.groupby("Subreddit")["Sentiment"].value_counts().unstack().fillna(0)
st.bar_chart(trend)
