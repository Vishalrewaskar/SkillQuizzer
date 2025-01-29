# app.py
import streamlit as st
import os
import re
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Session state initialization
if 'questions' not in st.session_state:
    st.session_state.questions = []
if 'answers' not in st.session_state:
    st.session_state.answers = {}
if 'score' not in st.session_state:
    st.session_state.score = 0

def extract_video_id(url):
    regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu.be\/)([^&\n?#]+)"
    match = re.search(regex, url)
    return match.group(1) if match else None

def get_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = " ".join([chunk['text'] for chunk in transcript_list])
        return transcript
    except Exception as e:
        st.error(f"Error fetching transcript: {str(e)}")
        return None

def generate_questions(transcript):
    prompt = f"""**ROLE**: Expert MCQ Generator
**TASK**: Create 7 high-quality MCQs (5 medium, 2 hard) from this text:
{transcript[:5000]}

**FORMAT RULES**:
[Question_X]
Difficulty: medium/hard
Question: Clear question text
Options:
A) Plausible option
B) Plausible option
C) Plausible option
D) Plausible option
Correct: Letter only

**QUALITY CHECKS**:
1. Questions must test understanding
2. Options must be distinct
3. Avoid trivial/obvious questions
4. Ensure single correct answer

Generate exactly 7 questions following these rules:"""

    try:
        response = model.generate_content(prompt)
        if not response.text:
            raise ValueError("Empty response from Gemini")
        return parse_questions(response.text)
    except Exception as e:
        st.error(f"Generation Error: {str(e)}")
        return None

def parse_questions(text):
    questions = []
    question_blocks = text.split('[Question_')[1:]
    
    for block in question_blocks:
        try:
            q = {
                'difficulty': "Medium",
                'question': "",
                'options': {},
                'answer': ""
            }
            
            # Extract components
            q['difficulty'] = re.search(r"Difficulty:\s*(medium|hard)", block, re.IGNORECASE).group(1).capitalize()
            q['question'] = re.search(r"Question:\s*(.+?)\nOptions:", block, re.DOTALL).group(1).strip()
            
            # Extract options
            options_text = re.search(r"Options:\s*(.+?)\nCorrect:", block, re.DOTALL).group(1).strip()
            q['options'] = {opt[0].upper(): opt[1].strip() 
                           for opt in re.findall(r"([A-D])\)\s*(.+)", options_text)}
            
            # Extract answer
            q['answer'] = re.search(r"Correct:\s*([A-D])", block).group(1).upper()
            
            # Validate
            if all([q['question'], len(q['options']) == 4, q['answer']]):
                questions.append(q)
                
        except Exception as e:
            continue  # Skip malformed questions
            
    return questions[:7]  # Return max 7 valid questions

def generate_certificate(name, video_title, filename="certificate.pdf"):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Design
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height-150, "Certificate of Completion")
    
    c.setFont("Helvetica", 18)
    c.drawCentredString(width/2, height-200, f"This certifies that {name}")
    c.drawCentredString(width/2, height-240, "has successfully completed the course:")
    c.drawCentredString(width/2, height-280, f"'{video_title}'")
    
    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(width/2, height-350, f"Date: {datetime.now(pytz.utc).strftime('%Y-%m-%d')}")
    c.drawCentredString(width/2, height-380, f"Certificate ID: {os.urandom(8).hex()}")
    
    c.rect(50, 50, width-100, height-100)
    c.save()
    return filename

# Streamlit UI
st.title("YouTube Quiz Generator 🎓")

# Step 1: URL Input
url = st.text_input("Enter YouTube URL:")
if url:
    video_id = extract_video_id(url)
    if video_id:
        st.video(f"https://www.youtube.com/watch?v={video_id}")
        
        if st.button("Generate Quiz"):
            with st.spinner("Fetching transcript and generating questions..."):
                transcript = get_transcript(video_id)
                if transcript:
                    st.session_state.questions = generate_questions(transcript)
                    st.session_state.answers = {}
                    st.session_state.score = 0

# Step 2: Display Questions
if st.session_state.questions:
    st.header("Quiz Time! 🧠")
    for i, q in enumerate(st.session_state.questions):
        st.subheader(f"Q{i+1}: {q['question']}")
        st.caption(f"Difficulty: {q['difficulty']}")
        
        options = list(q['options'].items())
        user_answer = st.radio(
            f"Select answer for Q{i+1}",
            options=[f"{k}) {v}" for k, v in options],
            key=f"question_{i}"
        )
        st.session_state.answers[i] = user_answer[0]

# Step 3: Scoring
if st.session_state.questions and st.button("Submit Answers"):
    correct = 0
    for i, q in enumerate(st.session_state.questions):
        if st.session_state.answers.get(i, '') == q['answer']:
            correct += 1
    st.session_state.score = (correct / len(st.session_state.questions)) * 100
    
    st.success(f"Your score: {st.session_state.score:.1f}%")
    
    if st.session_state.score >= 70:
        st.balloons()
        st.subheader("🎉 Congratulations! Earn Your Certificate")
        
        name = st.text_input("Enter your name for the certificate:")
        if name:
            cert_file = generate_certificate(name, "YouTube Course")
            with open(cert_file, "rb") as f:
                st.download_button(
                    "Download Certificate",
                    f.read(),
                    file_name=cert_file,
                    mime="application/pdf"
                )
    else:
        st.warning("Try again! You need 70% or higher to get the certificate.")
