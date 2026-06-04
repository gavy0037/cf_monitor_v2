from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from datetime import datetime
from database import Base

class UserProfile(Base):
    __tablename__ = "user_profile"

    cf_handle = Column(String, primary_key=True, index=True)
    current_rating = Column(Integer, default=0)
    max_rating = Column(Integer, default=0)
    last_fetched = Column(DateTime, default=datetime.utcnow)
    last_backfill_date = Column(String, nullable=True)  # 'YYYY-MM-DD', tracks last successful backfill

class DailyStats(Base):
    __tablename__ = "daily_stats"

    handle = Column(String, primary_key=True, index=True)
    date = Column(String, primary_key=True, index=True) # 'YYYY-MM-DD'
    accepted_count = Column(Integer, default=0)
    wa_count = Column(Integer, default=0)
    average_difficulty = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProblemLog(Base):
    __tablename__ = "problem_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    handle = Column(String, index=True)
    problem_id = Column(String, index=True) # e.g., '1800C'
    problem_title = Column(String)
    rating = Column(Integer, nullable=True)
    status = Column(String) # 'AC', 'FAILED', 'UP_SOLVING'
    mistake_category = Column(String, nullable=True)
    custom_notes = Column(Text, nullable=True)
    solved_date = Column(String, index=True) # 'YYYY-MM-DD'
    created_at = Column(DateTime, default=datetime.utcnow)

class CodeforcesContest(Base):
    __tablename__ = "codeforces_contests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    start_time_seconds = Column(Integer)
    phase = Column(String)
