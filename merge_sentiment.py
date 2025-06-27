import json
from pathlib import Path

# Define paths
warren_path = Path("warrensoutputfile.json")
sentiment_path = Path("sentiment/swaggystocks_sentiment.json")
output_path = Path("combined_output.json")

# Load data
with open(warren_path, "r") as f:
    warren_data = json.load(f)

with open(sentiment_path, "r") as f:
    swaggy_data = json.load(f)

# Combine
combined = {
    "warren_scan": warren_data,
    "wallstreetbets_sentiment": swaggy_data.get("wallstreetbets_sentiment", []),
    "unusual_options_activity": swaggy_data.get("unusual_options_activity", [])
}

# Save
with open(output_path, "w") as f:
    json.dump(combined, f, indent=2)

print(f"✅ Combined file created: {output_path}")
