import pandas as pd

INPUT_FILE  = "sales-data.csv"
OUTPUT_FILE = "below_average_price_per_sqft.csv"

# Load the CSV
df = pd.read_csv(INPUT_FILE)
print(f"Total properties loaded: {len(df)}")

df = df[df["sq__ft"] > 0]
print(f"Properties with valid sqft: {len(df)}")

# Calculate price per sqft for each property
df["price_per_sqft"] = df["price"] / df["sq__ft"]

# Work out the average
average = df["price_per_sqft"].mean()
print(f"Average price per sqft: ${average:,.2f}")

# Keep only properties below the average
below_average = df[df["price_per_sqft"] < average].copy()
print(f"Properties below average: {len(below_average)}")

# Drop the helper column and save
below_average.drop(columns=["price_per_sqft"]).to_csv(OUTPUT_FILE, index=False)
print(f"Done — results saved to '{OUTPUT_FILE}'")
