from fastapi import FastAPI, HTTPException, Query
import uvicorn
import sqlite3
import os
import requests
import subprocess
import markdown
import duckdb
import speech_recognition as sr
from PIL import Image
from git import Repo

app = FastAPI()

# Database path and AI Proxy settings
db_path = "./data/task_history.db"
AIPROXY_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
AIPROXY_TOKEN = os.getenv("AIPROXY_TOKEN")
if not AIPROXY_TOKEN:
    raise ValueError("AIPROXY_TOKEN is not set in environment variables")

# Initialize SQLite Database
def init_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        '''CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY, 
            task TEXT, 
            status TEXT, 
            output TEXT
        )'''
    )
    conn.commit()
    conn.close()

init_db()

# Secure path validation to ensure access remains within "./data"
def is_valid_path(path: str) -> bool:
    abs_path = os.path.abspath(path)
    allowed_base = os.path.abspath("./data")
    return abs_path.startswith(allowed_base)

# Function to execute shell commands safely
def run_command(command: str):
    tokens = command.split()
    # Check if any token exactly equals "rm" or "unlink"
    if "rm" in tokens or "unlink" in tokens:
        raise HTTPException(status_code=400, detail="File deletion is not allowed")
    
    # Ensure command accesses only "./data/" by checking tokens individually
    if not any(token.startswith("./data") for token in tokens):
        raise HTTPException(status_code=400, detail="Access outside ./data is not allowed")
    
    try:
        result = subprocess.run(command, shell=True, text=True, capture_output=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            raise Exception(result.stderr.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run")
def run_task(task: str = Query(..., description="Task description in plain English")):
    try:
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are an automation assistant. Generate only a single valid shell command."},
                {"role": "user", "content": task}
            ]
        }
        response = requests.post(AIPROXY_URL, json=data, headers=headers)
        response_json = response.json()
        print("AI Proxy response:", response_json)
        if "choices" not in response_json:
            raise HTTPException(status_code=response.status_code, detail=f"Invalid AI Proxy response: {response_json}")
        
        command = response_json["choices"][0]["message"]["content"].strip()

        # Remove markdown code fences if present.
        if command.startswith("```") and command.endswith("```"):
            lines = command.splitlines()
            # Remove the first and last lines containing the fences (and language tag, if any)
            command = "\n".join(lines[1:-1]).strip()
        
        # Execute the shell command securely
        output = run_command(command)
        
        # Store task result in SQLite
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("INSERT INTO tasks (task, status, output) VALUES (?, ?, ?)", (task, "success", output))
        conn.commit()
        conn.close()
        
        return {"status": "success", "output": output}
    except HTTPException as e:
        return {"status": "error", "message": str(e.detail)}


@app.get("/read")
def read_file(path: str = Query(..., description="File path to read")):
    if not is_valid_path(path):
        raise HTTPException(status_code=400, detail="Access outside ./data is not allowed")
    
    try:
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="File not found")
        with open(path, "r") as file:
            content = file.read()
        return {"status": "success", "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Business Task Endpoints

@app.post("/fetch_api")
def fetch_api(url: str, output_path: str):
    if not is_valid_path(output_path):
        raise HTTPException(status_code=400, detail="Access outside ./data is not allowed")
    response = requests.get(url)
    with open(output_path, "w") as f:
        f.write(response.text)
    return {"status": "success", "message": "Data fetched"}

@app.post("/git_commit")
def git_commit(repo_url: str, commit_message: str):
    repo_path = "./data/repo"
    if os.path.exists(repo_path):
        repo = Repo(repo_path)
    else:
        repo = Repo.clone_from(repo_url, repo_path)
    repo.git.add(all=True)
    repo.index.commit(commit_message)
    repo.remote().push()
    return {"status": "success", "message": "Commit pushed"}

@app.post("/run_sql")
def run_sql(db_path: str, query: str):
    if not is_valid_path(db_path):
        raise HTTPException(status_code=400, detail="Access outside ./data is not allowed")
    conn = duckdb.connect(db_path)
    result = conn.execute(query).fetchall()
    conn.close()
    return {"status": "success", "result": result}

@app.post("/convert_md")
def convert_md_to_html(md_path: str, output_path: str):
    if not is_valid_path(md_path) or not is_valid_path(output_path):
        raise HTTPException(status_code=400, detail="Access outside ./data is not allowed")
    with open(md_path, "r") as f:
        html_content = markdown.markdown(f.read())
    with open(output_path, "w") as f:
        f.write(html_content)
    return {"status": "success", "message": "Markdown converted to HTML"}

@app.post("/transcribe_audio")
def transcribe_audio(audio_path: str):
    if not is_valid_path(audio_path):
        raise HTTPException(status_code=400, detail="Access outside ./data is not allowed")
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)
    transcription = recognizer.recognize_google(audio)
    return {"status": "success", "transcription": transcription}

@app.post("/resize_image")
def resize_image(image_path: str, width: int, height: int):
    if not is_valid_path(image_path):
        raise HTTPException(status_code=400, detail="Access outside ./data is not allowed")
    img = Image.open(image_path)
    resized_img = img.resize((width, height))
    # Save the resized image to the same path
    resized_img.save(image_path)
    return {"status": "success", "message": "Image resized"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

