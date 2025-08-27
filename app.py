from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKENS_DIR = "tokens"
VIDEOS_DIR = "videos"
os.makedirs(TOKENS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local testing
    allow_methods=["*"],
    allow_headers=["*"],
)



class VideoData(BaseModel): 
    filename: str
    title: str
    description: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    profile: str

def get_authenticated_service(profile: str):
    token_path = os.path.join(TOKENS_DIR, f"{profile}.json")
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secrets.json", SCOPES
        )
        creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)

def upload_video(youtube, video_path, title, description, publish_time):
    body = {
        "snippet": {"title": title, "description": description, "categoryId": "22"},
        "status": {"privacyStatus": "private", "publishAt": publish_time, "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    return response

import os

@app.post("/upload/")
async def upload_videos(videos: List[VideoData]):
    results = []
    for vid in videos:
        video_path = os.path.join(VIDEOS_DIR, vid.filename)
        if not os.path.exists(video_path):
            results.append({"filename": vid.filename, "status": "file not found"})
            continue

        publish_datetime = f"{vid.date}T{vid.time}:00Z"
        youtube = get_authenticated_service(vid.profile)
        try:
            response = upload_video(youtube, video_path, vid.title, vid.description, publish_datetime)
            results.append({"filename": vid.filename, "status": "uploaded", "video_id": response["id"]})
            
            # Delete the video file after successful upload
            os.remove(video_path)

        except Exception as e:
            results.append({"filename": vid.filename, "status": f"failed: {e}"})
    return {"results": results}


@app.get("/accounts/")
def list_accounts():
    return {"accounts": [f.replace(".json","") for f in os.listdir(TOKENS_DIR) if f.endswith(".json")]}

@app.post("/add-account/")
def add_account(profile_name: str = Form(...)):
    # OAuth flow will save token as profile_name.json
    creds_path = os.path.join(TOKENS_DIR, f"{profile_name}.json")
    flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
    creds = flow.run_local_server(port=0)
    with open(creds_path, "w") as f:
        f.write(creds.to_json())
    return {"status": "account added", "profile": profile_name}


@app.post("/upload-file/")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(VIDEOS_DIR, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"status": "uploaded", "filename": file.filename}


@app.delete("/delete-account/{profile}")
def delete_account(profile: str):
    token_path = os.path.join(TOKENS_DIR, f"{profile}.json")
    if os.path.exists(token_path):
        os.remove(token_path)
        return {"status": "deleted", "profile": profile}
    raise HTTPException(status_code=404, detail=f"Profile '{profile}' not found")