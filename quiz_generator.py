import os
import json
import requests
from datetime import datetime, date
from sheets_utils import connect_google_sheets, load_sheet

def get_previous_sprint_movies(current_date):
    """Get movies from the previous sprint"""
    try:
        # Load sprints data
        sprints_data = load_sheet("Sprints")
        
        # Load suggestions data
        suggestions_data = load_sheet("Suggestions")
        
        # Find previous sprint (the one that ended most recently before today)
        previous_sprint = None
        for sprint in sorted(sprints_data, key=lambda x: x['end_date'], reverse=True):
            end_date = datetime.strptime(sprint['end_date'], '%Y-%m-%d').date()
            if end_date < current_date:
                previous_sprint = sprint
                break
        
        if not previous_sprint:
            print("❌ No previous sprint found")
            return None, None
        
        # Filter movies for previous sprint
        previous_sprint_movies = [
            {
                "movie_name": s['movie_name'],
                "genre": s.get('genre', ''),
                "year": ""  # You might want to add year to your suggestions sheet
            }
            for s in suggestions_data 
            if s.get('sprint') == previous_sprint['sprint_id']
        ]
        
        print(f"🎬 Found {len(previous_sprint_movies)} movies from sprint {previous_sprint['sprint_id']}")
        return previous_sprint_movies, previous_sprint['sprint_id']
        
    except Exception as e:
        print(f"❌ Error getting previous sprint movies: {e}")
        return None, None

def generate_ai_quiz(movies_data, sprint_id):
    """Call Groq AI to generate quiz data"""
    groq_api_key = os.getenv('GROQ_API_KEY')
    
    if not groq_api_key:
        print("❌ GROQ_API_KEY not found")
        return None
    
    # Prepare prompt
    prompt = f"""
    Analyze these movies from movie club sprint {sprint_id} and create comprehensive quiz data:
    
    Movies Data:
    {json.dumps(movies_data, indent=2)}
    
    For EACH movie, provide:
    1. Two multiple-choice questions with 4 options each (A, B, C, D) and clearly mark the correct answer
    2. One best quote from the movie
    3. One fun trivia fact about the movie
    
    Format your response as JSON with this exact structure:
    {{
        "sprint_id": "{sprint_id}",
        "generated_date": "{datetime.now().isoformat()}",
        "movies_quiz_data": [
            {{
                "movie_name": "Movie Name",
                "multiple_choice_questions": [
                    {{
                        "question": "Question text?",
                        "options": [
                            "A. Option A text",
                            "B. Option B text", 
                            "C. Option C text",
                            "D. Option D text"
                        ],
                        "correct_answer": "A. Option A text"
                    }},
                    {{
                        "question": "Second question?",
                        "options": [
                            "A. Option A text",
                            "B. Option B text",
                            "C. Option C text", 
                            "D. Option D text"
                        ],
                        "correct_answer": "B. Option B text"
                    }}
                ],
                "best_quote": "Most memorable quote from the movie",
                "fun_trivia": "Interesting fun fact about the movie"
            }}
        ]
    }}
    
    Important:
    - Create 2 questions per movie
    - Include the letter (A, B, C, D) in both options and correct answers
    - Make questions about plot, characters, actors, director, or interesting facts
    - Ensure quotes are authentic and memorable
    - Provide unique trivia that fans would find interesting
    - Return ONLY valid JSON, no additional text
    """
    
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messages": [{"role": "user", "content": prompt}],
        "model": "llama-3.1-8b-instant",
        "temperature": 0.7,
        "max_tokens": 4000,
        "stream": False
    }
    
    try:
        print("🚀 Calling Groq API...")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Try to parse JSON response
            try:
                quiz_data = json.loads(content)
                print(f"✅ Successfully generated quiz for {len(quiz_data['movies_quiz_data'])} movies")
                return quiz_data
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse AI response as JSON: {e}")
                print(f"Raw response: {content}")
                return None
        else:
            print(f"❌ Groq API error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def save_quiz_to_sheet(sprint_id, quiz_json):
    """Save quiz data to QuizInfo sheet"""
    try:
        sheet = connect_google_sheets()
        
        # Try to get existing QuizInfo sheet, create if it doesn't exist
        try:
            quiz_ws = sheet.worksheet("QuizInfo")
        except:
            quiz_ws = sheet.add_worksheet(title="QuizInfo", rows="1000", cols="3")
            # Add headers
            quiz_ws.append_row(["sprint_id", "quiz_json", "timestamp"])
        
        # Check if quiz already exists for this sprint
        existing_data = quiz_ws.get_all_records()
        for idx, row in enumerate(existing_data, start=2):
            if row['sprint_id'] == sprint_id:
                # Update existing row
                quiz_ws.update(f'B{idx}:C{idx}', [[
                    json.dumps(quiz_json),
                    datetime.now().isoformat()
                ]])
                print(f"✅ Updated existing quiz for sprint {sprint_id}")
                return
        
        # Add new row
        quiz_ws.append_row([
            sprint_id,
            json.dumps(quiz_json),
            datetime.now().isoformat()
        ])
        print(f"✅ Saved new quiz for sprint {sprint_id}")
        
    except Exception as e:
        print(f"❌ Error saving to sheet: {e}")

def check_quiz_exists(sprint_id):
    """Check if quiz already exists for a sprint"""
    try:
        quiz_data = load_sheet("QuizInfo")
        return any(q.get('sprint_id') == sprint_id for q in quiz_data)
    except:
        return False

def generate_quiz_for_previous_sprint():
    """Main function to generate and save quiz for previous sprint"""
    print("🎬 Starting AI Quiz Generation...")
    
    # Get today's date
    today = date.today()
    print(f"📅 Today's date: {today}")
    
    # Get movies from previous sprint
    movies_data, sprint_id = get_previous_sprint_movies(today)
    
    if not movies_data or not sprint_id:
        print("❌ No movies found for previous sprint")
        return False
    
    # Check if quiz already exists for this sprint
    if check_quiz_exists(sprint_id):
        print(f"ℹ️ Quiz already exists for sprint {sprint_id}, skipping...")
        return False
    
    # Generate AI quiz
    quiz_data = generate_ai_quiz(movies_data, sprint_id)
    
    if quiz_data:
        # Save to Google Sheets
        save_quiz_to_sheet(sprint_id, quiz_data)
        print("✅ Quiz generation completed successfully!")
        return True
    else:
        print("❌ Failed to generate quiz")
        return False
