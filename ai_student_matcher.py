import csv
import os
import base64
from openai import AzureOpenAI
import json

# get environment variables from .env file
from dotenv import load_dotenv
load_dotenv(override=True)

subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment = os.getenv("DEPLOYMENT_NAME")
endpoint = os.getenv("ENDPOINT_URL")

# Initialize Azure OpenAI client with key-based authentication
client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=subscription_key,
    api_version="2025-01-01-preview",
)

# Prepare the chat prompt
chat_prompt = [
    {
        "role": "developer",
        "content": [
            {
                "type": "text",
                "text": "You are an AI assistant that helps people find information."
            }
        ]
    }
]

# For each name in the /REAL_DATA/GPN Sydney 2025 - 3 Start of Day.csv file, look in the /REAL_DATA/attendee-report-2025-T3.csv and find the matching entry by using the completion model
# Paths to CSV files
SURVEY_FILE = "REAL_DATA/GPN Sydney 2025 – 3 Start of Day.csv"
ATTENDEE_FILE = "REAL_DATA/attendee-report-2025-T3.csv"

def read_csv(file_path):
    """Read CSV file and return list of dictionaries"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        # Try with a different encoding
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            print(f"Still can't read {file_path}: {e}")
            return []

def find_match_with_ai(survey_student, attendee_list):
    """Use Azure OpenAI to find the best match for a survey student in the attendee list"""
    
    # Extract the survey student name
    survey_name = survey_student.get("Full name to display on certificate", "")
    survey_school = survey_student.get("What school do you go to?", "")
    survey_year = survey_student.get("I am currently in...", "")
    
    # Prepare prompt for the AI
    attendees_info = []
    for i, attendee in enumerate(attendee_list, 1):
        attendee_name = attendee.get("Student's full name", "")
        attendee_school = attendee.get("What school does the student attend?", "")
        attendee_year = attendee.get("What year is the student in at school?", "")
        attendees_info.append(f"{i}. Name: {attendee_name}, School: {attendee_school}, Year: {attendee_year}")
    
    attendees_text = "\n".join(attendees_info)
    
    prompt = f"""I need to match a student from a survey with their registration in an attendee list.
                Survey Student Information:
                - Name: {survey_name}
                - School: {survey_school}
                - Year: {survey_year}

                Attendee List:
                {attendees_text}

                Find the best match for the survey student in the attendee list. 
                Consider name variations, nicknames, and possible misspellings.
                Return your answer as a JSON object with these fields:
                - match_index: the number of the matching attendee (1-based index from the list)
                - confidence: your confidence level (0-100)
                - reasoning: brief explanation of why this is a match

                If there's no good match, set match_index to 0 and explain why.
        """

    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are a helpful assistant that specializes in matching student names across different databases. You're good at recognizing nicknames, abbreviations, and misspellings."
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
    ]

    try:
        completion = client.chat.completions.create(
            model=deployment,
            messages=messages,
            response_format={"type": "json_object"},
            max_completion_tokens=1000,
        )
        
        response_text = completion.choices[0].message.content
        
        # Parse JSON response
        try:
            result = json.loads(response_text)
            return result
        except json.JSONDecodeError:
            print(f"Error parsing JSON response: {response_text}")
            return {"match_index": 0, "confidence": 0, "reasoning": "Error parsing AI response"}
            
    except Exception as e:
        print(f"Error getting completion: {e}")
        return {"match_index": 0, "confidence": 0, "reasoning": f"Error: {str(e)}"}

def main():
    # Read the CSV files
    print("Reading CSV files...")
    survey_students = read_csv(SURVEY_FILE)
    attendees = read_csv(ATTENDEE_FILE)
    
    if not survey_students or not attendees:
        print("Failed to read one or both CSV files")
        return
    
    print(f"Found {len(survey_students)} survey students and {len(attendees)} attendees")
    
    # Prepare results
    results = []
    
    # Process each survey student
    for i, student in enumerate(survey_students):
        print(f"Processing student {i+1}/{len(survey_students)}: {student.get('Full name to display on certificate', '')}")
        
        # Find match using AI
        match_result = find_match_with_ai(student, attendees)
        
        # Get the matched attendee (if any)
        matched_attendee = None
        if match_result.get("match_index", 0) > 0:
            matched_attendee_idx = match_result.get("match_index", 0) - 1
            if 0 <= matched_attendee_idx < len(attendees):
                matched_attendee = attendees[matched_attendee_idx]
                print(matched_attendee["Student's full name"])
        
        # Add to results
        results.append({
            "survey_name": student.get("Full name to display on certificate", ""),
            "survey_school": student.get("What school do you go to?", ""),
            "survey_year": student.get("I am currently in...", ""),
            "survey_dietary": student.get("Do you have any dietary requirements for lunch time?", ""),
            "attendee_name": matched_attendee.get("Student's full name", "") if matched_attendee else "",
            "attendee_school": matched_attendee.get("What school does the student attend?", "") if matched_attendee else "",
            "attendee_year": matched_attendee.get("What year is the student in at school?", "") if matched_attendee else "",
            "attendee_dietary": matched_attendee.get("Dietary requirements", "") if matched_attendee else "",
            "ticket_buyer": (f"{matched_attendee.get('Buyer first name', '')} {matched_attendee.get('Buyer last name', '')}").strip() if matched_attendee else "",
            "checked_in": matched_attendee.get("Checked in", "") if matched_attendee else "",
            "confidence": match_result.get("confidence", 0),
            "reasoning": match_result.get("reasoning", "")
        })
    
    # Write results to CSV
    output_file = "ai_student_matches.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = results[0].keys() if results else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Results written to {output_file}")
    
    # Summary statistics
    matches = [r for r in results if r["attendee_name"]]
    print(f"\nMatching Summary:")
    print(f"Total students in survey: {len(survey_students)}")
    print(f"Successfully matched: {len(matches)} ({len(matches)/len(survey_students)*100:.1f}%)")
    print(f"Unmatched: {len(survey_students) - len(matches)}")
    
    # Print high confidence matches
    high_conf = [r for r in results if r["confidence"] >= 90]
    medium_conf = [r for r in results if 70 <= r["confidence"] < 90]
    low_conf = [r for r in results if 0 < r["confidence"] < 70]
    
    print(f"\nConfidence levels:")
    print(f"High confidence (90-100%): {len(high_conf)}")
    print(f"Medium confidence (70-89%): {len(medium_conf)}")
    print(f"Low confidence (1-69%): {len(low_conf)}")
    print(f"No match (0%): {len(results) - len(high_conf) - len(medium_conf) - len(low_conf)}")

if __name__ == "__main__":
    main()