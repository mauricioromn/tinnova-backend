from dotenv import load_dotenv
import os

load_dotenv()

print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("SUPABASE_SERVICE_ROLE:", "OK" if os.getenv("SUPABASE_SERVICE_ROLE") else "MISSING")
print("AWS_ACCESS_KEY:", "OK" if os.getenv("AWS_ACCESS_KEY_ID") else "MISSING")
print("AWS_SECRET_KEY:", "OK" if os.getenv("AWS_SECRET_ACCESS_KEY") else "MISSING")
print("S3_BUCKET:", os.getenv("S3_BUCKET"))
