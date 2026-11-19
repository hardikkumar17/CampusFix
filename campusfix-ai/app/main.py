
import json
import mimetypes
import os
import smtplib
import uuid
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware

from app.graph import app as campus_graph


# --------------------------------
# 1. Configuration
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

DATA_FILE = BASE_DIR / "data" / "maintenance_records.json"


# --------------------------------
# 2. Initialize FastAPI
# --------------------------------

app = FastAPI(
    title="CampusFix AI",
    description="Agentic AI Campus Maintenance Assistant",
    version="1.0"
)

# --------------------------------
# 3. Allow React Frontend Access
# --------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# --------------------------------
# 4. Email notification to authority
# --------------------------------

def send_complaint_mail(
    complaint: str,
    location: str,
    diagnosis: str,
    decision: dict,
    image_path: Path | None = None,
):
    """Runs in the background. A mail failure never breaks the complaint."""

    try:
        sender = os.getenv("MAIL_USER")
        password = os.getenv("MAIL_PASS")
        recipient = os.getenv("AUTHORITY_EMAIL")

        if not (sender and password and recipient):
            print("Email skipped: MAIL_USER / MAIL_PASS / AUTHORITY_EMAIL missing in .env")
            return

        msg = EmailMessage()
        msg["Subject"] = (
            f"[{decision.get('priority', 'New')}] "
            f"Campus complaint: {location}"
        )
        msg["From"] = sender
        msg["To"] = recipient
        msg.set_content(
            f"A new complaint was registered on CampusFix.\n\n"
            f"Location: {location}\n"
            f"Complaint: {complaint}\n\n"
            f"Urgency: {decision.get('urgency', 'N/A')}\n"
            f"Priority: {decision.get('priority', 'N/A')}\n"
            f"Next action: {decision.get('next_action', 'N/A')}\n\n"
            f"AI diagnosis:\n{diagnosis}\n"
        )

        if image_path and Path(image_path).exists():
            content_type, _ = mimetypes.guess_type(str(image_path))
            maintype, subtype = (
                content_type or "application/octet-stream"
            ).split("/")

            msg.add_attachment(
                Path(image_path).read_bytes(),
                maintype=maintype,
                subtype=subtype,
                filename=Path(image_path).name,
            )

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)

        print("Email sent to authority.")

    except Exception as error:
        print("Email error:", str(error))


# --------------------------------
# 5. Maintenance Records Endpoint
# --------------------------------

@app.get("/api/maintenance-records")
def get_maintenance_records():

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            records = json.load(file)

        return {
            "success": True,
            "total": len(records),
            "records": records
        }

    except Exception as error:
        print("Maintenance records error:", str(error))
        raise HTTPException(
            status_code=500,
            detail="Unable to load maintenance records."
        )


# --------------------------------
# 6. Health Check Endpoint
# --------------------------------

@app.get("/")
def home():

    return {
        "message": "CampusFix AI Backend is running!"
    }


# --------------------------------
# 7. Complaint Processing Endpoint
# --------------------------------

@app.post("/api/complaint")
def process_complaint(
    background_tasks: BackgroundTasks,
    complaint: str = Form(...),
    location: str = Form("Not specified"),
    image: UploadFile | None = File(None),
):

    if not complaint.strip():
        raise HTTPException(
            status_code=400,
            detail="Please enter a complaint."
        )

    # ---- Save the uploaded image (optional) ----
    image_path = None

    if image and image.filename:

        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Only JPG, PNG or WEBP images are allowed."
            )

        data = image.file.read()

        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Image must be smaller than 5 MB."
            )

        extension = Path(image.filename).suffix.lower() or ".jpg"
        image_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{extension}"
        image_path.write_bytes(data)

    # ---- Run the AI workflow ----
    try:
        full_complaint = (
            f"Location: {location}. "
            f"Complaint: {complaint}"
        )

        result = campus_graph.invoke({
            "complaint": full_complaint,
            "activities": []
        })

        decision = result.get("decision", {})

        # ---- Email the authority in the background ----
        background_tasks.add_task(
            send_complaint_mail,
            complaint,
            location,
            result["diagnosis"],
            decision,
            image_path,
        )

        return {
            "success": True,
            "complaint": complaint,
            "location": location,
            "diagnosis": result["diagnosis"],
            "recommendation": result["recommendation"],
            "activities": result.get("activities", []),
            "decision": decision,
            "image_attached": image_path is not None
        }

    except Exception as error:
        print("Complaint processing error:", str(error))

        raise HTTPException(
            status_code=500,
            detail="Unable to process complaint. Please try again."
        )
