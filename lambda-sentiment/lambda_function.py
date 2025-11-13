import json
import boto3
import os
import pandas as pd
from io import StringIO

# Initialize AWS clients
s3 = boto3.client('s3', region_name='us-east-1')
comprehend = boto3.client('comprehend', region_name='us-east-1')

OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'reddit-ml-vikas')

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        # Load Reddit data
        obj = s3.get_object(Bucket=bucket, Key=key)
        posts = json.loads(obj['Body'].read().decode('utf-8'))

        results = []
        for post in posts:
            text = post.get('Title', '')
            if text.strip():
                try:
                    sentiment = comprehend.detect_sentiment(Text=text, LanguageCode='en')
                    post['Sentiment'] = sentiment['Sentiment']
                    post['SentimentScore'] = sentiment['SentimentScore']
                except Exception as e:
                    post['Sentiment'] = 'ERROR'
                    post['Error'] = str(e)
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

        # ✅ Convert to CSV and save to S3
        df = pd.DataFrame(results)
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
