from flask import Flask, render_template, request

import moviepy.config as mpy_config

mpy_config.change_settings({
    "IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16\magick.exe"
})

import os
import uuid

import fitz
from docx import Document
from gtts import gTTS
from googletrans import Translator

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ColorClip,
    ImageClip,
    concatenate_videoclips
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

    # PDF
    if filepath.endswith(".pdf"):

        doc = fitz.open(filepath)

        for page in doc:
            text += page.get_text("text") + "\n"

    # DOCX
    elif filepath.endswith(".docx"):

        doc = Document(filepath)

        for para in doc.paragraphs:
            text += para.text + "\n"

    return text


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

    # -----------------------------------
    # AUTO BACKGROUND COLOR
    # -----------------------------------
    bg_color = (20, 20, 20)

    if "software" in lower_text or "technology" in lower_text:
        bg_color = (10, 10, 70)

    elif "health" in lower_text:
        bg_color = (0, 70, 40)

    elif "education" in lower_text:
        bg_color = (80, 50, 0)

    elif "business" in lower_text:
        bg_color = (60, 0, 60)

    # -----------------------------------
    # BACKGROUND
    # -----------------------------------
    background = ColorClip(
        size=(720, 480),
        color=bg_color,
        duration=audio.duration
    )

    # -----------------------------------
    # SIMPLE TITLE
    # -----------------------------------
    title = TextClip(
        txt="AI Story Translation",
        fontsize=40,
        color='white',
        font='Arial'
    )

    # -----------------------------------
    # SIMPLE ANIMATION
    # -----------------------------------
    title = (
        title
        .set_position(
            lambda t: (
                'center',
                180 + (10 * __import__('math').sin(t))
            )
        )
        .set_duration(audio.duration)
    )

    # -----------------------------------
    # FINAL VIDEO
    # -----------------------------------
    final_video = CompositeVideoClip([
        background,
        title
    ])

    final_video = final_video.set_audio(audio)

    final_video.write_videofile(
        video_path,
        fps=12,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=2,
        logger=None
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

        <a href="/{video_file}" download="translated_video.mp4">
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

    <style>

    body{{
        font-family:Arial;
        padding:40px;
        background:#f4f4f4;
    }}

    button{{
        padding:12px 20px;
        background:#4CAF50;
        border:none;
        color:white;
        border-radius:8px;
        cursor:pointer;
    }}

    pre{{
        white-space: pre-wrap;
        background:white;
        padding:15px;
        border-radius:10px;
    }}

    </style>

    </head>

    <body>

    <h1>
        Magic Translation Machine ✔
    </h1>

    <hr>

    <h2>
        Translated Text ({lang})
    </h2>

    <pre>
{translated_text}
    </pre>

    <hr>

    <h2>Audio Output</h2>

    <audio controls controlsList="nodownload">
        <source src="/{audio_file}" type="audio/mp3">
    </audio>

    <br><br>

    <a href="/{audio_file}" download="translated_audio.mp3">
        <button>
            Download Audio
        </button>
    </a>

    <br><br>

    <hr>

    {video_html}

    </body>

    </html>

    """


# -----------------------------------
# RUN APP
# -----------------------------------
if __name__ == "__main__":

    app.run(debug=True)