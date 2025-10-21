import os
import json
import requests
from datetime import datetime, date
from sheets_utils_gh import connect_google_sheets, load_sheet  # Instead of sheets_utils

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
    
    CRITICAL REQUIREMENTS FOR QUESTIONS:
    - DO NOT create generic questions like "What is the plot?", "Where does the story take place?", "Who is the main character?", "Who directed this movie?", "Who acted in this movie?"
    - Create SPECIFIC and INTERESTING questions about plot details, memorable scenes, character motivations, or unique aspects
    - Questions should test DEEPER knowledge of the movie, not basic facts
    - Example good question: "What is the name of the water planet in Interstellar where one hour equals seven years on Earth?"
    - Example good question: "In Inception, what personal item does Cobb use to test if he's in reality or a dream?"
    - Example good question: "What object does Andy Dufresne use to hide his escape tunnel in Shawshank Redemption?"
    
    FORMAT REQUIREMENTS:
    Format your response as JSON with this exact structure:
    {{
        "sprint_id": "{sprint_id}",
        "generated_date": "{datetime.now().isoformat()}",
        "movies_quiz_data": [
            {{
                "movie_name": "Movie Name",
                "multiple_choice_questions": [
                    {{
                        "question": "Specific and interesting question about plot detail?",
                        "options": [
                            "A. Option A text",
                            "B. Option B text", 
                            "C. Option C text",
                            "D. Option D text"
                        ],
                        "correct_answer": "A. Option A text"
                    }},
                    {{
                        "question": "Another specific question about memorable scene?",
                        "options": [
                            "A. Option A text",
                            "B. Option B text",
                            "C. Option C text", 
                            "D. Option D text"
                        ],
                        "correct_answer": "B. Option B text"
                    }}
                ],
                "best_quote": "Most memorable and authentic quote from the movie",
                "fun_trivia": "Interesting behind-the-scenes fact or production detail"
            }}
        ]
    }}
    
    QUALITY CHECKS - DOUBLE VERIFY BEFORE RESPONDING:
    - Verify ALL questions are specific and test deeper movie knowledge
    - Verify NO generic questions about plot, setting, director, or actors
    - Verify ALL answers are factually correct
    - Verify quotes are authentic and memorable (not made up)
    - Verify trivia is interesting and accurate
    - Verify exactly 2 questions per movie
    - Verify 4 options per question with clear correct answer
    - Verify JSON structure is perfect with no syntax errors
    
    Return ONLY valid JSON, no additional text or explanations.
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
                
                # Additional validation
                for movie in quiz_data['movies_quiz_data']:
                    for question in movie['multiple_choice_questions']:
                        q_text = question['question'].lower()
                        # Check for forbidden question types
                        forbidden_phrases = ['what is the plot', 'who directed', 'who is the director', 
                                           'who acted', 'who stars', 'who plays', 'main character',
                                           'where does', 'when does', 'what year', 'genre of']
                        if any(phrase in q_text for phrase in forbidden_phrases):
                            print(f"⚠️ Warning: Question may be too generic: {question['question']}")
                
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


if __name__ == "__main__":
    # Debug info
    print("🚀 Starting quiz generator...")
    print(f"GROQ_API_KEY exists: {bool(os.getenv('GROQ_API_KEY'))}")
    print(f"GOOGLE_SHEET_URL exists: {bool(os.getenv('GOOGLE_SHEET_URL'))}")
    
    # Generate quiz
    success = generate_quiz_for_previous_sprint()
    
    print(f"Script completed: {'SUCCESS' if success else 'NO ACTION TAKEN'}")
    
    # Exit with appropriate code for GitHub Actions
    exit(0 if success else 1)
