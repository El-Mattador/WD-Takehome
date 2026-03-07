import pandas as pd

df = pd.read_csv("manual syllabus LO.csv")
df = df.ffill()
df["loId"] = df["Primary Level"].astype(str) + ":" + df["Sub-Strand"] + ":" + df["Ref"].astype(str)
df.to_csv("manual syllabus LO filled.csv", index=False)

print(f"Saved {len(df)} rows to 'manual syllabus LO filled.csv'")
