from flask import Flask, render_template, request

import moviepy.config as mpy_config

mpy_config.change_settings({
    "IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16\magick.exe"
})

import os
import uuid

import math  # Fixes the yellow underline on 'math'
from moviepy.editor import *

import fitz
from docx import Document
from gtts import gTTS
from googletrans import Translator

from moviepy.editor import (
    TextClip,
    AudioFileClip,
    CompositeVideoClip,
    ColorClip
)

app = Flask(__name__)

# -----------------------------------
# FOLDER SETUP
# -----------------------------------
UPLOAD_FOLDER = "static/uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

translator = Translator()

# -----------------------------------
# EXTRACT TEXT
# -----------------------------------
def extract_text(filepath):
    text = ""
    if filepath.endswith(".pdf"):
        doc = fitz.open(filepath)
        for page in doc:
            # Join lines that were broken by PDF formatting
            page_text = page.get_text("text").replace('\n', ' ')
            text += page_text + " "
    elif filepath.endswith(".docx"):
        doc = Document(filepath)
        for para in doc.paragraphs:
            text += para.text + " "
    
    # Final cleanup: Replace multiple spaces with one space
    return " ".join(text.split())


# -----------------------------------
# SPLIT TEXT
# -----------------------------------
def split_text(text, size=500):

    return [
        text[i:i + size]
        for i in range(0, len(text), size)
    ]


# -----------------------------------
# TRANSLATE TEXT
# -----------------------------------
def translate_text(text, lang):

    if lang == "en":
        return text

    chunks = split_text(text)

    translated_result = ""

    for chunk in chunks:

        try:

            translated = translator.translate(
                chunk,
                dest=lang
            ).text

            translated_result += translated + " "

        except:

            translated_result += chunk + " "

    return translated_result


# -----------------------------------
# VIDEO GENERATION
# -----------------------------------
def generate_video(text, audio_path, video_path, lang):

    audio = AudioFileClip(audio_path)
    lower_text = text.lower()

    # 1. SET BACKGROUND COLOR
    bg_color = (20, 20, 20)
    if "software" in lower_text or "technology" in lower_text:
        bg_color = (10, 10, 70)
    elif "health" in lower_text:
        bg_color = (0, 70, 40)
    elif "education" in lower_text:
        bg_color = (80, 50, 0)
    elif "business" in lower_text:
        bg_color = (60, 0, 60)

    # 2. SELECT FONT
    if lang == "bn":
        font_path = "fonts/NotoSansBengali-Regular.ttf"
    elif lang == "hi":
        font_path = "fonts/NotoSansDevanagari-Regular.ttf"
    else:
        font_path = "Arial"

    # 3. CREATE INITIAL TEXT CLIP (to measure height)
    content = TextClip(
        txt=text,
        fontsize=28,
        color='white',
        size=(620, None),
        method='caption',
        font=font_path,
        align='center',
        interline=10
    )

    # 1. Calculate the total distance the text needs to travel
    # # We want the text to start at 350 and end near the top (0)
    total_distance = content.h + 280

    # 2. Calculate speed: Distance / Time
    # This ensures the text movement is perfectly synced to the audio length
    scroll_speed = total_distance / audio.duration

    # 5. APPLY ANIMATION AND DURATION
   # This adds a subtle "sway" (2 pixels left/right) so the text feels like it's floating
    content = (
        content
        .set_position(lambda t: (
            360 - (content.w / 2) + (2 * math.sin(t * 2)), # Subtle horizontal float
            350 - (t * scroll_speed)                        # Your scrolling logic
        ))
        .set_duration(audio.duration)
        .crossfadein(1.5) # Smoothly fades in the text
    )

    # 6. ASSEMBLE FINAL VIDEO
    background = ColorClip(size=(720, 480), color=(10, 12, 16)).set_duration(audio.duration)

    # We define 'glow' here so the final_video knows what it is
    glow = (
        ColorClip(size=(400, 300), color=(25, 30, 45))
        .set_opacity(0.4)
        .set_position('center')
        .set_duration(audio.duration)
        .crossfadein(2.0)
    )
    
    # Add a semi-transparent black overlay to make text pop
    vignette = ColorClip(size=(720, 480), color=(0,0,0)).set_opacity(0.3).set_duration(audio.duration)
    
    
    final_video = CompositeVideoClip([background, glow, vignette, content])
    final_video = final_video.set_audio(audio)

    final_video.write_videofile(
        video_path,
        fps=15,
        codec="libx264",
        preset="ultrafast",
        threads=4 # Speeds up rendering
    )

    return video_path

    # -----------------------------------
    # SHORT TEXT
    # -----------------------------------
    full_display_text = text

    # -----------------------------------
    # FONT FIX
    # -----------------------------------
    if lang == "bn":
        font_path = os.path.join("fonts", "NotoSansBengali-Regular.ttf")
    elif lang == "hi":
        font_path = os.path.join("fonts", "NotoSansDevanagari-Regular.ttf")
    else:
        font_path = "Arial" # Standard English font

    # -----------------------------------
    # TEXT CLIP
    # -----------------------------------
    content = TextClip(
        txt=full_display_text,
        fontsize=22,
        color='white',
        size=(620, None),
        method='caption',
        font=font_path,
        align='center',
        interline=10
    )

    # -----------------------------------
    # UPWARD ANIMATION
    # -----------------------------------
    content = (
        content
        .set_position(
            lambda t: (
                'center',
                350 - (t * scroll_speed)
            )
        )
        .set_duration(audio.duration)
    )

    # -----------------------------------
    # FINAL VIDEO
    # -----------------------------------
    final_video = CompositeVideoClip([
        background,
        content
    ])

    final_video = final_video.set_audio(audio)

    final_video.write_videofile(
        video_path,
        fps=15,
        codec="libx264",
        preset="ultrafast"
    )

    return video_path


# -----------------------------------
# HOME ROUTE
# -----------------------------------
@app.route("/")
def home():

    return render_template("index.html")


# -----------------------------------
# GENERATE ROUTE
# -----------------------------------
@app.route("/generate", methods=["POST"])
def generate():

    file = request.files["file"]

    lang = request.form.get("language", "en")

    if file.filename == "":
        return "No file selected"

    # -----------------------------------
    # UNIQUE FILE NAME
    # -----------------------------------
    file_id = str(uuid.uuid4())

    filepath = os.path.join(
        UPLOAD_FOLDER,
        file_id + "_" + file.filename
    )

    file.save(filepath)

    # -----------------------------------
    # STEP 1: EXTRACT TEXT
    # -----------------------------------
    text = extract_text(filepath)

    # -----------------------------------
    # STEP 2: TRANSLATE
    # -----------------------------------
    translated_text = translate_text(text, lang)

    # -----------------------------------
    # STEP 3: GENERATE AUDIO
    # -----------------------------------
    audio_file = f"static/uploads/{file_id}.mp3"

    try:

        tts = gTTS(
            text=translated_text,
            lang=lang,
            slow=False
        )

        tts.save(audio_file)

    except Exception as e:

        return f"""
        <h2>Audio Generation Failed ❌</h2>
        <p>{str(e)}</p>
        """

    # -----------------------------------
    # STEP 4: GENERATE VIDEO
    # -----------------------------------
    video_file = f"static/uploads/{file_id}.mp4"

    try:

        generate_video(
            translated_text,
            audio_file,
            video_file,
            lang
        )

        video_html = f"""

        <h2>Generated Video</h2>

        <video width="650" controls>
            <source src="/{video_file}" type="video/mp4">
        </video>

        <br><br>

        <a href="/{video_file}" download>
            <button>
                Download Video
            </button>
        </a>
        """

    except Exception as e:

        video_html = f"""
        <h2>Video Generation Failed ❌</h2>
        <p>{str(e)}</p>
        """

    # -----------------------------------
    # FINAL OUTPUT
    # -----------------------------------
    return f"""
<html>
<head>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 40px;
            background: radial-gradient(circle at top right, #1e1b4b, #0f172a); /* Matches your deep blue/purple bg */
            color: white;
            display: flex;
            justify-content: center;
            min-height: 100vh;
        }}

        .container {{
            background: rgba(255, 255, 255, 0.05); /* Glass effect */
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 28px;
            padding: 40px;
            width: 100%;
            max-width: 650px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            text-align: center;
        }}

        h1 {{ font-size: 28px; margin-bottom: 10px; background: linear-gradient(to right, #fff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        h2 {{ font-size: 18px; opacity: 0.9; margin-top: 30px; font-weight: 500; }}

        pre {{
            white-space: pre-wrap;
            background: rgba(0, 0, 0, 0.2);
            padding: 20px;
            border-radius: 15px;
            text-align: left;
            font-size: 14px;
            line-height: 1.6;
            border: 1px solid rgba(255, 255, 255, 0.05);
            max-height: 200px;
            overflow-y: auto;
        }}

        .btn-audio {{
            background: rgba(255, 255, 255, 0.1);
            color: #22d3ee;
            border: 1px solid rgba(34, 211, 238, 0.3);
            padding: 12px 24px;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
            width: 100%;
            margin-top: 10px;
        }}

        .btn-video {{
            background: linear-gradient(90deg, #8e2de2, #4a00e0); /* Purple gradient from your UI */
            color: white;
            border: none;
            padding: 16px 24px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            width: 100%;
            margin-top: 15px;
            box-shadow: 0 10px 15px -3px rgba(142, 45, 226, 0.4);
            transition: transform 0.2s;
        }}

        .btn-video:hover {{ transform: translateY(-2px); }}

        audio {{ width: 100%; margin-top: 10px; filter: invert(100%) hue-rotate(180deg) brightness(1.5); }} /* Makes audio player match dark theme */
        video {{ border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.1); margin-top: 10px; }}
        
        hr {{ border: 0; border-top: 1px solid rgba(255, 255, 255, 0.1); margin: 30px 0; }}
    </style>
</head>
<body>

<div class="container">
    <h1>Magic Translation Machine ✨</h1>
    <p style="opacity: 0.6; font-size: 14px;">Your document has been processed successfully.</p>

    <hr>

    <h2>Translated Text ({lang})</h2>
    <pre>{translated_text}</pre>

    <hr>

    <h2>Audio Narration</h2>
    <audio controls controlsList="nodownload">
        <source src="/{audio_file}" type="audio/mp3">
    </audio>
    
    <a href="/{audio_file}" download="translated_audio.mp3" style="text-decoration:none;">
        <button class="btn-audio">Download Audio</button>
    </a>

    <hr>

    <h2>Video Output</h2>
    <!-- This replaces {video_html} with an aesthetic video player -->
    <video width="100%" controls style="margin-bottom: 10px;">
        <source src="/{video_file}" type="video/mp4">
    </video>

    <a href="/{video_file}" download="translated_video.mp4" style="text-decoration:none;">
        <button class="btn-video">Download Video</button>
    </a>
</div>

</body>
</html>
"""


# -----------------------------------
# RUN APP
# -----------------------------------
if __name__ == "__main__":

    app.run(debug=True)