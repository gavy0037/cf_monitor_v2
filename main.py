from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, date as date_type, timedelta
import os

from database import engine, Base, get_db
import models, schemas, cf_client

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Codeforces Progress Monitor")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/dashboard")
def get_dashboard(handle: str = Query("Gavy0037"), db: Session = Depends(get_db)):
    # 1. Fetch user info from CF API
    cf_user = cf_client.get_user_info(handle)
    if not cf_user:
        raise HTTPException(status_code=404, detail=f"Codeforces handle '{handle}' not found.")
    
    current_rating = cf_user.get("rating", 0)
    max_rating = cf_user.get("maxRating", 0)
    rank = cf_user.get("rank", "unrated")
    
    # Update local UserProfile cache
    db_profile = db.query(models.UserProfile).filter(models.UserProfile.cf_handle == handle).first()
    if not db_profile:
        db_profile = models.UserProfile(cf_handle=handle)
        db.add(db_profile)
    
    db_profile.current_rating = current_rating
    db_profile.max_rating = max_rating
    db_profile.last_fetched = datetime.utcnow()
    db.commit()
    
    # 2. Fetch user submissions from CF API
    submissions = cf_client.get_user_status(handle, count=150)
    
    # 3. Calculate daily statistics (using UTC)
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    accepted_today = 0
    wa_today = 0
    total_difficulty_today = 0
    
    # Track unique problems solved today to prevent double counting ACs
    solved_problems_today = set()
    
    for sub in submissions:
        creation_time = sub.get("creationTimeSeconds", 0)
        sub_date_str = datetime.utcfromtimestamp(creation_time).strftime('%Y-%m-%d')
        
        if sub_date_str == today_str:
            verdict = sub.get("verdict")
            prob = sub.get("problem", {})
            prob_id = f"{prob.get('contestId')}{prob.get('index')}"
            
            if verdict == "OK" and prob_id not in solved_problems_today:
                solved_problems_today.add(prob_id)
                accepted_today += 1
                total_difficulty_today += prob.get("rating", 0)
            elif verdict != "OK":
                wa_today += 1
    
    avg_difficulty = 0.0
    if accepted_today > 0:
        avg_difficulty = round(total_difficulty_today / accepted_today, 1)
        
    # Cache daily statistics in daily_stats table
    db_stats = db.query(models.DailyStats).filter(models.DailyStats.date == today_str, models.DailyStats.handle == handle).first()
    if not db_stats:
        db_stats = models.DailyStats(date=today_str, handle=handle)
        db.add(db_stats)
    
    db_stats.accepted_count = accepted_today
    db_stats.wa_count = wa_today
    db_stats.average_difficulty = avg_difficulty
    db.commit()
    
    return {
        "cf_handle": handle,
        "rating": current_rating,
        "rank": rank,
        "accepted_today": accepted_today,
        "wa_today": wa_today,
        "average_difficulty_today": avg_difficulty,
        "recent_submissions": submissions[:30] # Return top 30 submissions
    }

@app.get("/api/backfill/{handle}")
def backfill_history(handle: str, db: Session = Depends(get_db)):
    """
    Fetch submissions from CF API and backfill daily_stats
    for the past 5 days (excluding today) for the given handle.
    Called once on login to pre-populate historical data.
    """
    # Check if historical data already exists for this handle
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    existing_history = db.query(models.DailyStats).filter(
        models.DailyStats.handle == handle,
        models.DailyStats.date < today_str
    ).first()
    
    if existing_history:
        return {"handle": handle, "message": "Historical data already exists. Skipping backfill.", "backfilled_dates": [], "summary": []}

    submissions = cf_client.get_user_status(handle, count=500)
    if not submissions:
        raise HTTPException(status_code=404, detail=f"No submissions found for handle '{handle}'.")

    # Build date range: past 5 days (not including today)
    today = datetime.utcnow().date()
    target_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 6)]

    # Group submissions by date
    day_buckets: dict = {d: {"ac": set(), "wa": 0, "difficulties": []} for d in target_dates}

    for sub in submissions:
        creation_time = sub.get("creationTimeSeconds", 0)
        sub_date_str = datetime.utcfromtimestamp(creation_time).strftime('%Y-%m-%d')

        if sub_date_str not in day_buckets:
            continue

        verdict = sub.get("verdict")
        prob = sub.get("problem", {})
        prob_id = f"{prob.get('contestId')}{prob.get('index')}"

        if verdict == "OK" and prob_id not in day_buckets[sub_date_str]["ac"]:
            day_buckets[sub_date_str]["ac"].add(prob_id)
            rating = prob.get("rating", 0)
            if rating:
                day_buckets[sub_date_str]["difficulties"].append(rating)
        elif verdict != "OK":
            day_buckets[sub_date_str]["wa"] += 1

    # Upsert into daily_stats for each target date
    for date_str, bucket in day_buckets.items():
        ac_count = len(bucket["ac"])
        wa_count = bucket["wa"]
        diffs = bucket["difficulties"]
        avg_diff = round(sum(diffs) / len(diffs), 1) if diffs else 0.0

        db_stats = db.query(models.DailyStats).filter(models.DailyStats.date == date_str, models.DailyStats.handle == handle).first()
        if not db_stats:
            db_stats = models.DailyStats(date=date_str, handle=handle)
            db.add(db_stats)

        db_stats.accepted_count = ac_count
        db_stats.wa_count = wa_count
        db_stats.average_difficulty = avg_diff

    db.commit()

    return {
        "handle": handle,
        "backfilled_dates": target_dates,
        "summary": [
            {
                "date": d,
                "ac": len(day_buckets[d]["ac"]),
                "wa": day_buckets[d]["wa"],
                "avg_difficulty": round(sum(day_buckets[d]["difficulties"]) / len(day_buckets[d]["difficulties"]), 1)
                    if day_buckets[d]["difficulties"] else 0.0
            }
            for d in target_dates
        ]
    }

@app.get("/api/history")
def get_history(handle: str, db: Session = Depends(get_db)):
    history = db.query(models.DailyStats).filter(models.DailyStats.handle == handle).order_by(models.DailyStats.date.desc()).all()
    return history

@app.get("/api/history/{date}")
def get_history_detail(date: str, handle: str, db: Session = Depends(get_db)):
    # Get stats for the day
    stats = db.query(models.DailyStats).filter(models.DailyStats.date == date, models.DailyStats.handle == handle).first()
    
    # Get mistake logs for the day
    logs = db.query(models.ProblemLog).filter(models.ProblemLog.solved_date == date, models.ProblemLog.handle == handle).all()
    
    return {
        "date": date,
        "stats": stats,
        "logs": logs
    }

@app.post("/api/logs", response_model=schemas.ProblemLogResponse)
def create_problem_log(log_in: schemas.ProblemLogCreate, db: Session = Depends(get_db)):
    # Create the problem log entry
    db_log = models.ProblemLog(
        handle=log_in.handle,
        problem_id=log_in.problem_id,
        problem_title=log_in.problem_title,
        rating=log_in.rating,
        status=log_in.status,
        mistake_category=log_in.mistake_category,
        custom_notes=log_in.custom_notes,
        solved_date=log_in.solved_date
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

@app.get("/api/contests/upsolve")
def get_upsolve_tracker(handle: str = Query("Gavy0037"), db: Session = Depends(get_db)):
    # Fetch recent submissions
    submissions = cf_client.get_user_status(handle, count=250)
    
    # Identify unique contests the user submitted to
    # We will look at the last 5 contests based on submission time
    contests_map = {}
    for sub in submissions:
        contest_id = sub.get("contestId")
        if not contest_id or contest_id >= 10000:  # Skip gym contests
            continue
        
        prob = sub.get("problem", {})
        prob_index = prob.get("index", "")
        verdict = sub.get("verdict")
        
        if contest_id not in contests_map:
            contests_map[contest_id] = {
                "contest_id": contest_id,
                "problems_submitted": set(),
                "problems_solved": set(),
            }
            
        contests_map[contest_id]["problems_submitted"].add(prob_index)
        if verdict == "OK":
            contests_map[contest_id]["problems_solved"].add(prob_index)
            
    # Sort contests descending
    sorted_contest_ids = sorted(contests_map.keys(), reverse=True)[:5]
    
    results = []
    for cid in sorted_contest_ids:
        c_info = contests_map[cid]
        # We want to check if they submitted anything during/after contest, and what status 'C' is
        c_problems = list(c_info["problems_submitted"])
        solved = "C" in c_info["problems_solved"]
        attempted = "C" in c_info["problems_submitted"]
        
        status = "Not Attempted"
        if solved:
            status = "Upsolved" if not attempted else "Solved" # If they solved it, they did it!
        elif attempted:
            status = "Attempted but Failed"
            
        # Try to guess contest name (e.g. from index or fetch if needed, but we keep it lightweight)
        results.append({
            "contest_id": cid,
            "submitted_problems": sorted(c_problems),
            "c_status": status,
            "c_solved": solved
        })
        
    return results

# Serve Frontend static files
frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
