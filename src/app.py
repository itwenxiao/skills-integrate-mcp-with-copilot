"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path
from typing import Dict, List

# SQLAlchemy imports
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# --- Database setup (SQLite + SQLAlchemy) ---
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./activities.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Activity(Base):
    __tablename__ = "activities"
    name = Column(String, primary_key=True, index=True)
    description = Column(Text)
    schedule = Column(String)
    max_participants = Column(Integer)
    participants = relationship("Participant", back_populates="activity", cascade="all, delete-orphan")


class Participant(Base):
    __tablename__ = "participants"
    id = Column(Integer, primary_key=True)
    email = Column(String, index=True)
    activity_name = Column(String, ForeignKey("activities.name"))
    activity = relationship("Activity", back_populates="participants")


def init_db(seed_data: Dict[str, Dict] | None = None):
    Base.metadata.create_all(bind=engine)
    # seed if empty
    db = SessionLocal()
    try:
        any_activity = db.query(Activity).first()
        if not any_activity and seed_data:
            for name, info in seed_data.items():
                act = Activity(
                    name=name,
                    description=info.get("description", ""),
                    schedule=info.get("schedule", ""),
                    max_participants=info.get("max_participants", 0),
                )
                db.add(act)
                db.flush()  # ensure act is persisted for FK
                for email in info.get("participants", []):
                    p = Participant(email=email, activity=act)
                    db.add(p)
            db.commit()
    finally:
        db.close()


# Initial in-memory data used only for seeding the DB on first run
initial_activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.on_event("startup")
def startup_event():
    # Initialize DB and seed if necessary
    init_db(seed_data=initial_activities)


def activities_to_dict(db):
    """Read DB activity objects and convert to the previous dict shape."""
    result: Dict[str, Dict] = {}
    activities = db.query(Activity).all()
    for act in activities:
        result[act.name] = {
            "description": act.description,
            "schedule": act.schedule,
            "max_participants": act.max_participants,
            "participants": [p.email for p in act.participants]
        }
    return result


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    db = SessionLocal()
    try:
        return activities_to_dict(db)
    finally:
        db.close()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity (persistent)."""
    db = SessionLocal()
    try:
        act = db.query(Activity).filter(Activity.name == activity_name).first()
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found")

        # Validate student is not already signed up
        if any(p.email == email for p in act.participants):
            raise HTTPException(status_code=400, detail="Student is already signed up")

        # Check max participants
        if act.max_participants and len(act.participants) >= act.max_participants:
            raise HTTPException(status_code=400, detail="Activity is full")

        participant = Participant(email=email, activity=act)
        db.add(participant)
        db.commit()
        return {"message": f"Signed up {email} for {activity_name}"}
    finally:
        db.close()


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity (persistent)."""
    db = SessionLocal()
    try:
        act = db.query(Activity).filter(Activity.name == activity_name).first()
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found")

        participant = db.query(Participant).filter(Participant.activity_name == activity_name, Participant.email == email).first()
        if not participant:
            raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

        db.delete(participant)
        db.commit()
        return {"message": f"Unregistered {email} from {activity_name}"}
    finally:
        db.close()
