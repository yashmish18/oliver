import pandas as pd
import numpy as np
import json

# Load the enrollment data to understand the structure
df = pd.read_csv('enorllment.2025.csv')
print("CSV Structure:")
print(df.head())
print(f"\nTotal records: {len(df)}")
print(f"Columns: {df.columns.tolist()}")
print("\nUnique semesters:", df['Student Session'].unique())
print("Unique subjects:", df['Subject Name'].nunique())
print("\nSubject distribution:")
print(df['Subject Name'].value_counts().head(10))