import os, boto3
from dotenv import load_dotenv
load_dotenv()

bucket = os.getenv("S3_BUCKET")
assert bucket, "Falta S3_BUCKET"

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

key = "diagnostics/hello.txt"
s3.put_object(Bucket=bucket, Key=key, Body=b"hola tinnova")
url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600)
print("OK S3 subido:", f"s3://{bucket}/{key}")
print("URL temporal (1h):", url)

