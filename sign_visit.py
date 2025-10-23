#!/usr/bin/env python3
import sys, hmac, hashlib, os
from dotenv import load_dotenv
load_dotenv()

SECRET = os.getenv("SECRET_KEY","change_this_secret").encode()

def sign(visit_id: str) -> str:
    return hmac.new(SECRET, visit_id.encode(), hashlib.sha256).hexdigest()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/sign_visit.py <VISIT_ID>")
        sys.exit(1)
    print(sign(sys.argv[1]))
