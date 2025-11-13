import streamlit as st
import boto3
import pandas as pd
from io import StringIO
from sklearn.feature_extraction.text import TfidfVectorizer

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

# ---------- Overview ----------
st.subheader("Dataset Overview")
st.write(df.head())

col1, col2, col3 = st.columns(3)
col1.metric("Total Posts", len(df))
col2.metric("Positive Posts", (df['Sentiment'] == 'POSITIVE').sum())
col3.metric("Negative Posts", (df['Sentiment'] == 'NEGATIVE').sum())


# ---------- Top Authors by Sentiment ----------
st.subheader("🏆 Top Authors by Average Sentiment Score")

# Convert SentimentScore string to usable numeric (Positive - Negative)
df["NetSentiment"] = df["SentimentScore"].apply(
    lambda x: eval(x)["Positive"] - eval(x)["Negative"] if isinstance(x, str) else 0
)

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

# ---------- Compute Scores ----------
df["Positive"] = df["SentimentScore"].apply(lambda x: eval(x)["Positive"] if isinstance(x, str) else 0)
df["Negative"] = df["SentimentScore"].apply(lambda x: eval(x)["Negative"] if isinstance(x, str) else 0)

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

positive_titles = df[df["Sentiment"] == "POSITIVE"]["Title"].dropna().tolist()

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


