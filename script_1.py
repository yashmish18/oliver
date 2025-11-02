# Clean column names and analyze data structure
df.columns = ['Student Session', 'Student Roll Number', 'Student Name', 'Subject Code', 'Subject Name']

# Analyze the data for different semesters
print("Detailed Analysis:")
print("="*50)

semester_analysis = df.groupby('Student Session').agg({
    'Subject Name': ['count', 'nunique'],
    'Student Roll Number': 'nunique'
}).round(2)

print("Analysis by Semester:")
print(semester_analysis)

# Get course distribution by semester
print("\nTop courses by semester:")
for semester in ['SEMESTER 2', 'SEMESTER 4', 'SEMESTER 6', 'SEMESTER 8']:
    print(f"\n{semester}:")
    semester_courses = df[df['Student Session'] == semester]['Subject Name'].value_counts().head(5)
    print(semester_courses)
    
# Create sample data for rooms and seating
print("\nCreating sample room configurations...")
room_data = [
    {
        "room_id": "LT-001",
        "room_name": "Large Theater 1", 
        "capacity": 120,
        "layout": "theater",
        "rows": 12,
        "cols_per_row": [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10],
        "building": "Academic Block A"
    },
    {
        "room_id": "AUD-001", 
        "room_name": "Main Auditorium",
        "capacity": 200,
        "layout": "auditorium", 
        "rows": 15,
        "cols_per_row": [8, 10, 12, 14, 14, 16, 16, 16, 16, 14, 14, 12, 10, 8, 6],
        "building": "Central Building"
    },
    {
        "room_id": "CR-101",
        "room_name": "Classroom 101",
        "capacity": 60,
        "layout": "grid",
        "rows": 6, 
        "cols_per_row": [10, 10, 10, 10, 10, 10],
        "building": "Academic Block B"
    },
    {
        "room_id": "LAB-201",
        "room_name": "Computer Lab 201", 
        "capacity": 80,
        "layout": "island",
        "rows": 8,
        "cols_per_row": [10, 10, 10, 10, 10, 10, 10, 10],
        "building": "IT Building"
    },
    {
        "room_id": "HALL-001",
        "room_name": "Examination Hall 1",
        "capacity": 150,
        "layout": "grid", 
        "rows": 10,
        "cols_per_row": [15, 15, 15, 15, 15, 15, 15, 15, 15, 15],
        "building": "Exam Block"
    }
]

# Save processed data
rooms_df = pd.DataFrame(room_data)
print("Sample rooms created:")
print(rooms_df[['room_id', 'room_name', 'capacity', 'rows']].head())

# Save to CSV files for the application
df.to_csv('processed_enrollment.csv', index=False)
rooms_df.to_csv('rooms_config.csv', index=False)

print("\nData files created:")
print("- processed_enrollment.csv")
print("- rooms_config.csv")