"""Encode service_account.json to base64 and write to credentials/service_account_b64.txt"""
import base64, os

sa_path = os.path.join(os.path.dirname(__file__), "credentials", "service_account.json")
out_path = os.path.join(os.path.dirname(__file__), "credentials", "service_account_b64.txt")

with open(sa_path, "rb") as f:
    data = f.read()

b64 = base64.b64encode(data).decode("ascii")

with open(out_path, "w") as f:
    f.write(b64)

print(f"✅ Base64 encoded service account written to:\n   {out_path}")
print(f"\nLength: {len(b64)} characters")
print("\nFirst 60 chars (verify it looks like base64):")
print(b64[:60] + "...")
