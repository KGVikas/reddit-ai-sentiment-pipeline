import json
import boto3
import os
import pandas as pd
from io import StringIO

# Initialize AWS clients
s3 = boto3.client('s3', region_name='us-east-1')
comprehend = boto3.client('comprehend', region_name='us-east-1')

OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'reddit-ml-vikas')

def extract_text_from_post(post):
    # prefer lowercase 'title', then 'Title', then 'text' fields
    for key in ("title", "Title", "text", "body"):
        text = post.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""

def normalize_sentiment_result(sentiment):
    score = sentiment.get("SentimentScore", {})
    return {
        "Sentiment": sentiment.get("Sentiment", "NEUTRAL"),
        "Sentiment_Positive": float(score.get("Positive", 0.0)),
        "Sentiment_Negative": float(score.get("Negative", 0.0)),
        "Sentiment_Neutral": float(score.get("Neutral", 0.0)),
        "Sentiment_Mixed": float(score.get("Mixed", 0.0)),
    }

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        # Load Reddit data
        obj = s3.get_object(Bucket=bucket, Key=key)
        posts = json.loads(obj['Body'].read().decode('utf-8'))

        results = []
        for post in posts:
            text = extract_text_from_post(post)

            if not text:
                # Skip or mark as invalid 
                post['Sentiment'] = 'NO_TEXT'
                post['Sentiment_Positive'] = 0.0
                post['Sentiment_Negative'] = 0.0
                post['Sentiment_Neutral'] = 0.0
                post['Sentiment_Mixed'] = 0.0
                results.append(post)
                continue

            # Trim text to Comprehend limits (5KB);
            if len(text) > 4000:
                text = text[:4000]

            try:
                sentiment = comprehend.detect_sentiment(Text=text, LanguageCode='en')
                normalized = normalize_sentiment_result(sentiment)
                post['Sentiment'] = normalized['Sentiment']
                post['Sentiment_Positive'] = normalized['Sentiment_Positive']
                post['Sentiment_Negative'] = normalized['Sentiment_Negative']
                post['Sentiment_Neutral'] = normalized['Sentiment_Neutral']
                post['Sentiment_Mixed'] = normalized['Sentiment_Mixed']
            except Exception as e:
                post['Sentiment'] = 'ERROR'
                post['Sentiment_Error'] = str(e)
                post['Sentiment_Positive'] = 0.0
                post['Sentiment_Negative'] = 0.0
                post['Sentiment_Neutral'] = 0.0
                post['Sentiment_Mixed'] = 0.0

            results.append(post)

        # Save processed JSON
        raw_file_name = key.split('/')[-1]
        processed_file_name = raw_file_name.replace("reddit_raw_", "reddit_processed_")
        out_key = f"processed_data/{processed_file_name}"

        s3.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=out_key,
            Body=json.dumps(results, indent=2).encode('utf-8')
        )

        print(f"✅ Processed file saved as {processed_file_name}")

        # Convert to CSV and save to S3
        df = pd.DataFrame(results)

        for col in ['Sentiment_Positive','Sentiment_Negative','Sentiment_Neutral','Sentiment_Mixed']:
            if col not in df.columns:
                df[col] = 0.0

        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)

        csv_key = f"csv_data/{processed_file_name.replace('.json', '.csv')}"
        s3.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=csv_key,
            Body=csv_buffer.getvalue().encode('utf-8')
        )

        print(f"📁 CSV version saved to s3://{OUTPUT_BUCKET}/{csv_key}")

    return {
        'statusCode': 200,
        'message': 'Sentiment analysis complete',
        'output_location': f"s3://{OUTPUT_BUCKET}/processed_data/",
        'csv_location': f"s3://{OUTPUT_BUCKET}/csv_data/"
    }
