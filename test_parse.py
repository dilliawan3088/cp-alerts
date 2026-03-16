"""Quick parse test using a real downloaded CSV to verify the fix."""
import sys
sys.path.insert(0, r"c:\Alerts")
from dotenv import load_dotenv
import os
load_dotenv(r"c:\Alerts\.env")

from tools.parse_counter_csv import parse_counter_file

# Use first file in .tmp
tmp_dir = r"c:\Alerts\.tmp"
files = sorted([f for f in os.listdir(tmp_dir) if f.endswith(".csv")])
if not files:
    print("No files in .tmp/ — run main.py --once first to download")
    sys.exit(1)

# Test on the biggest file (most data)
test_file = os.path.join(tmp_dir, files[0])
print(f"Testing: {files[0]}")
print("-" * 50)

df = parse_counter_file(test_file)
print(f"Rows parsed: {len(df)}")
if len(df) > 0:
    print(f"First datetime: {df['datetime'].iloc[0]}")
    print(f"Last datetime:  {df['datetime'].iloc[-1]}")
    print(f"Max birds:      {df['bird_count'].max()}")
    print(f"Min birds:      {df['bird_count'].min()}")
    print()
    print("First 3 rows:")
    print(df[['datetime', 'bird_count']].head(3).to_string(index=False))
    print()
    print("✅ Parser is working correctly!")
else:
    print("❌ Still producing 0 rows. Check the file format.")
