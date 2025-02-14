import os
import subprocess
import json
import sqlite3
import duckdb
import pandas as pd
import requests
import shutil
from flask import Flask, request, jsonify, send_file
from PIL import Image
import markdown
import openai
from datetime import datetime

app = Flask(__name__)
DATA_DIR = "./data"
AIPROXY_TOKEN = os.getenv("AIPROXY_TOKEN")
openai.api_key = AIPROXY_TOKEN

def run_command(command):
    """ Run a shell command securely. """
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {"stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        return {"error": str(e)}

def run_sql(db_path, query):
    """ Execute a safe SQL query. """
    if not db_path.startswith("./data/"):
        return {"error": "Unauthorized database access"}
    if not query.strip().lower().startswith("select"):
        return {"error": "Only SELECT queries allowed"}
    try:
        conn = sqlite3.connect(db_path) if db_path.endswith(".db") else duckdb.connect(db_path)
        df = pd.read_sql(query, conn)
        conn.close()
        return df.to_dict()
    except Exception as e:
        return {"error": str(e)}

def resize_image(image_path, output_path, size=(256, 256)):
    """ Resize an image and save it. """
    try:
        img = Image.open(image_path)
        img = img.resize(size)
        img.save(output_path)
        return {"message": "Image resized"}
    except Exception as e:
        return {"error": str(e)}

def transcribe_audio(audio_path):
    """ Transcribe text from an MP3 file using OpenAI """
    try:
        with open(audio_path, "rb") as f:
            transcript = openai.Audio.transcribe(model="whisper-1", file=f)
        return {"text": transcript["text"]}
    except Exception as e:
        return {"error": str(e)}

def convert_md_to_html(md_path, output_path):
    """ Convert Markdown to HTML. """
    try:
        with open(md_path, "r") as f:
            md_content = f.read()
        html_content = markdown.markdown(md_content)
        with open(output_path, "w") as f:
            f.write(html_content)
        return {"message": "Markdown converted"}
    except Exception as e:
        return {"error": str(e)}

def count_wednesdays(input_file, output_file):
    """ Count the number of Wednesdays in a given date file. """
    date_formats = ["%Y-%m-%d", "%d-%b-%Y", "%Y/%m/%d %H:%M:%S", "%b %d, %Y"]
    
    def parse_date(date_str):
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    
    try:
        with open(input_file) as f:
            count = sum(1 for line in f if (dt := parse_date(line.strip())) and dt.weekday() == 2)
        with open(output_file, "w") as f:
            f.write(str(count))
        return {"message": "Counted Wednesdays"}
    except Exception as e:
        return {"error": str(e)}

@app.route("/run", methods=["POST"])
def run_task():
    """ Run a predefined task. """
    task = request.json.get("task")
    
    if task == "install_uv":
        return run_command("pip install uv")
    elif task == "format_markdown":
        return run_command("npx prettier@3.4.2 --write ./data/format.md")
    elif task == "count_wednesdays":
        return count_wednesdays("./data/dates.txt", "./data/dates-wednesdays.txt")
    elif task == "run_sql":
        db_path = request.json.get("db_path")
        query = request.json.get("query")
        return run_sql(db_path, query)
    elif task == "resize_image":
        return resize_image(
            request.json.get("image_path"),
            request.json.get("output_path"),
            tuple(request.json.get("size", [256, 256]))
        )
    elif task == "convert_md_to_html":
        return convert_md_to_html(
            request.json.get("md_path"),
            request.json.get("output_path")
        )
    else:
        return {"error": "Unknown task"}

@app.route("/read", methods=["GET"])
def read_file():
    """ Read the contents of a file """
    file_path = request.args.get("path")
    if not file_path.startswith("./data/"):
        return {"error": "Unauthorized file access"}, 403
    try:
        return send_file(file_path)
    except FileNotFoundError:
        return "", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
