# Reddit AI Sentiment Pipeline (AWS + Streamlit)

An end-to-end, serverless pipeline that automates extraction of Reddit posts, runs sentiment analysis using **Amazon Comprehend**, stores results in **S3** (JSON + CSV) and exposes insights via a production-ready **Streamlit** dashboard.

---

## 🚀 Project Summary
This project demonstrates a full serverless ETL + ML flow:
- **Extractor Lambda** (Python + `praw`) fetches posts from configured subreddits and stores deduplicated JSON in S3.
- **Sentiment Lambda** (Python + `boto3`) is triggered by S3 `PUT` events, calls **Amazon Comprehend**, enriches data with sentiment labels & scores, and writes both JSON and CSV outputs to S3.
- **Streamlit Dashboard** reads the latest CSV from S3 and visualizes KPIs, sentiment distribution, top authors, distinctive keywords, and clickable post links.

---

## 🔧 Features
- Fully **serverless** and automated via S3 event triggers.
- Data saved as both **JSON** (processed_data/) and **CSV** (csv_data/) for analysis.
- Streamlit dashboard auto-loads the latest CSV and supports subreddit filtering, limited-preview table, top-author metrics, TF-IDF keywords, and clickable links.
- Cost-conscious design (uses Lambda + Comprehend pay-per-use; fits comfortably within a small monthly budget).

---

## 🏗 Architecture

![Architecture](assets/architecture.png)

---

## Execution Video



https://github.com/user-attachments/assets/2add6c18-dc0f-4d86-a456-b65f59591984



---

## 📁 Repository Structure

```
├── README.md
├── lambda-extractor/ # Extract Lambda code 
│ └── lambda_function.py
├── lambda-sentiment/ # Sentiment Lambda code 
│ └── lambda_function.py
├── Dashboard/ # Streamlit dashboard
│ └── streamlit_app.py
├── assets/
│ └── architecture.png 
├── requirements.txt
```

---

## 🛠 Setup & Deployment (high-level)

### Prerequisites
- AWS account with permissions to create Lambda, S3, IAM, and use Comprehend.
- Reddit API credentials (create an app at https://www.reddit.com/prefs/apps).
- Local machine: Python 3.10+ and `pip`, or use Cloud IDE.

---

### 1) Create S3 bucket
- Bucket name example: `reddit-ml-vikas` (use your own unique name).
- Create folders (prefixes) will be used automatically:
  - `raw_data/to_process/`
  - `processed_data/`
  - `csv_data/`

Enable default encryption with **SSE-S3** (recommended).

---

### 2) IAM Role for Lambdas
Create an IAM role for Lambda with the following managed policies (or create least-privilege equivalents):
- `AmazonS3FullAccess` (or restrict to required S3 actions & bucket)
- `ComprehendFullAccess` (needed for sentiment Lambda)
- `AWSLambdaBasicExecutionRole` / `CloudWatchLogsFullAccess`

---

### 3) Extractor Lambda (reddit-extractor)
- Runtime: **Python 3.12**
- Code: `lambda-extractor/lambda_function.py`
- Attach PRAW as a layer (or package in deployment .zip).
- Environment variables:
  - `REDDIT_CLIENT_ID`
  - `REDDIT_CLIENT_SECRET`
  - `REDDIT_USER_AGENT`
  - `S3_BUCKET` (e.g., `reddit-ml-vikas`)
  - `SUBREDDITS` (comma-separated string)
  - `POST_LIMIT` (e.g., `10`)
  - `S3_PREFIX` (`raw_data/to_process/`)
- Handler: `lambda_function.lambda_handler`
- Memory: 256 MB, Timeout: 30–60s
- Behavior: fetches posts, deduplicates by `id`, writes JSON to `raw_data/to_process/`.

---

### 4) Sentiment Lambda (reddit-sentiment)
- Runtime: **Python 3.12**
- Code: `lambda-sentiment/lambda_function.py`
- Requires `pandas` (attach as Lambda layer) and `boto3` (available in runtime).
- Environment variables:
  - `OUTPUT_BUCKET` (same bucket)
- Add S3 event notification:
  - Event type: `s3:ObjectCreated:*`
  - Prefix: `raw_data/to_process/`
  - Destination: `reddit-sentiment` Lambda
- Behavior: reads uploaded JSON, calls Amazon Comprehend `detect_sentiment`, enriches data, writes processed JSON → `processed_data/` and CSV → `csv_data/`.

---

### 5) Streamlit Dashboard (local / cloud)
- File: `Dashboard/streamlit_app.py`
- Requirements (examples):
  ```text
  streamlit
  boto3
  pandas
  scikit-learn
