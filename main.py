from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, date as date_type, timedelta
from concurrent.futures import ThreadPoolExecutor
import os
import urllib.request
import json
import time

from database import engine, Base, get_db
import models, schemas, cf_client

# Initialize database tables
# Base.metadata.create_all(bind=engine) # Removed to prevent Vercel invocation crash on startup
app = FastAPI(title="Codeforces Progress Monitor")

# Cooldown for contest.list sync (seconds)
_last_contest_sync = 0
CONTEST_SYNC_COOLDOWN = 300  # 5 minutes

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
    # 1. Fetch user info AND submissions in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_user = executor.submit(cf_client.get_user_info, handle)
        future_subs = executor.submit(cf_client.get_user_status, handle, 150)
        cf_user = future_user.result()
        submissions = future_subs.result()
    
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
    Dynamically backfills daily_stats for all missing days since the last
    successful backfill. Uses last_backfill_date from UserProfile to compute
    the gap. Estimates submission count as gap_days * 40, capped at 1000.
    """
    today = datetime.utcnow().date()
    today_str = today.strftime('%Y-%m-%d')

    # Determine how far back to look
    profile = db.query(models.UserProfile).filter(models.UserProfile.cf_handle == handle).first()

    if profile and profile.last_backfill_date:
        last_date = datetime.strptime(profile.last_backfill_date, '%Y-%m-%d').date()
        gap_days = (today - last_date).days
    else:
        gap_days = 5  # Default for first-time users

    # Nothing to do if we already backfilled today
    if gap_days <= 0:
        return {"handle": handle, "message": "Already up to date.", "backfilled_dates": [], "summary": []}

    # Cap at 30 days max to keep things reasonable
    gap_days = min(gap_days, 30)

    # Build target dates (excluding today)
    target_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, gap_days + 1)]

    # Find which dates already have data
    existing_dates = set(
        row.date for row in db.query(models.DailyStats.date).filter(
            models.DailyStats.handle == handle,
            models.DailyStats.date.in_(target_dates)
        ).all()
    )

    missing_dates = [d for d in target_dates if d not in existing_dates]

    if not missing_dates:
        # All filled, just update the marker
        if profile:
            profile.last_backfill_date = today_str
            db.commit()
        return {"handle": handle, "message": "All recent days already backfilled.", "backfilled_dates": [], "summary": []}

    # Estimate how many submissions to pull: 40 per day, capped at 1000
    fetch_count = min(gap_days * 40, 1000)
    submissions = cf_client.get_user_status(handle, count=fetch_count)
    if not submissions:
        return {"handle": handle, "message": "No submissions found.", "backfilled_dates": [], "summary": []}

    # Group submissions only for missing dates
    day_buckets: dict = {d: {"ac": set(), "wa": 0, "difficulties": []} for d in missing_dates}

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

    # Insert stats only for missing dates
    for date_str, bucket in day_buckets.items():
        ac_count = len(bucket["ac"])
        wa_count = bucket["wa"]
        diffs = bucket["difficulties"]
        avg_diff = round(sum(diffs) / len(diffs), 1) if diffs else 0.0

        db_stats = models.DailyStats(date=date_str, handle=handle)
        db_stats.accepted_count = ac_count
        db_stats.wa_count = wa_count
        db_stats.average_difficulty = avg_diff
        db.add(db_stats)

    # Update the backfill marker
    if profile:
        profile.last_backfill_date = today_str

    db.commit()

    return {
        "handle": handle,
        "backfilled_dates": missing_dates,
        "summary": [
            {
                "date": d,
                "ac": len(day_buckets[d]["ac"]),
                "wa": day_buckets[d]["wa"],
                "avg_difficulty": round(sum(day_buckets[d]["difficulties"]) / len(day_buckets[d]["difficulties"]), 1)
                    if day_buckets[d]["difficulties"] else 0.0
            }
            for d in missing_dates
        ]
    }

@app.get("/api/history")
def get_history(handle: str, db: Session = Depends(get_db)):
    # Always attempt incremental backfill (it no-ops if all days are filled)
    try:
        backfill_history(handle, db)
    except Exception:
        pass
            
    history = db.query(models.DailyStats).filter(models.DailyStats.handle == handle).order_by(models.DailyStats.date.desc()).all()
    return history

def populate_database(handle: str, target_date: str, db: Session):
    submissions = cf_client.get_user_status(handle, count=300)
    
    ac_set = set()
    wa_count = 0
    difficulties = []
    
    if submissions:
        for sub in submissions:
            creation_time = sub.get("creationTimeSeconds", 0)
            sub_date_str = datetime.utcfromtimestamp(creation_time).strftime('%Y-%m-%d')
            
            if sub_date_str == target_date:
                verdict = sub.get("verdict")
                prob = sub.get("problem", {})
                prob_id = f"{prob.get('contestId')}{prob.get('index')}"
                
                if verdict == "OK" and prob_id not in ac_set:
                    ac_set.add(prob_id)
                    rating = prob.get("rating", 0)
                    if rating:
                        difficulties.append(rating)
                elif verdict != "OK":
                    wa_count += 1
                    
    ac_count = len(ac_set)
    avg_diff = round(sum(difficulties) / len(difficulties), 1) if difficulties else 0.0
    
    db_stats = models.DailyStats(
        date=target_date,
        handle=handle,
        accepted_count=ac_count,
        wa_count=wa_count,
        average_difficulty=avg_diff
    )
    db.add(db_stats)
    db.commit()

@app.get("/api/history/{date}")
def get_history_detail(date: str, handle: str, db: Session = Depends(get_db)):
    # Get stats for the day
    stats = db.query(models.DailyStats).filter(models.DailyStats.date == date, models.DailyStats.handle == handle).first()
    
    if not stats:
        populate_database(handle, date, db)
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

def sync_contests_background(db: Session):
    try:
        req = urllib.request.Request("https://codeforces.com/api/contest.list?gym=false", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10.0) as response:
            data = json.loads(response.read().decode())
        if data["status"] == "OK":
            contests = data["result"]
            # Find the top 10 finished CF contests
            finished = [c for c in contests if c.get("phase") == "FINISHED" and c.get("type") == "CF"][:10]
            for c in finished:
                db_contest = db.query(models.CodeforcesContest).filter(models.CodeforcesContest.id == c["id"]).first()
                if not db_contest:
                    db_contest = models.CodeforcesContest(
                        id=c["id"],
                        name=c["name"],
                        start_time_seconds=c.get("startTimeSeconds", 0),
                        phase=c.get("phase")
                    )
                    db.add(db_contest)
            db.commit()
    except Exception as e:
        print(f"Error syncing contests: {e}")

@app.get("/api/contests/tracker")
def get_contest_tracker(background_tasks: BackgroundTasks, handle: str = Query("Gavy0037"), db: Session = Depends(get_db)):
    # 1. Trigger background sync only if cooldown has elapsed
    global _last_contest_sync
    now = time.time()
    if now - _last_contest_sync > CONTEST_SYNC_COOLDOWN:
        _last_contest_sync = now
        background_tasks.add_task(sync_contests_background, db)
    
    # 2. Fetch the 5 most recent finished contests from DB
    latest_contests = db.query(models.CodeforcesContest).order_by(models.CodeforcesContest.start_time_seconds.desc()).limit(5).all()
    
    if not latest_contests:
        # If DB is empty, try to sync synchronously just this once
        sync_contests_background(db)
        latest_contests = db.query(models.CodeforcesContest).order_by(models.CodeforcesContest.start_time_seconds.desc()).limit(5).all()
        
    contest_ids = [c.id for c in latest_contests]
    
    # 3. Fetch user recent submissions
    submissions = cf_client.get_user_status(handle, count=300)
    
    # 4. Process submissions for those specific contests
    contests_map = {
        c.id: {
            "contest_id": c.id,
            "name": c.name,
            "problems_submitted": set(),
            "problems_solved": set(),
            "participation_type": "PRACTICE" # Default before checking
        } for c in latest_contests
    }
    
    for sub in submissions:
        cid = sub.get("contestId")
        if cid in contests_map:
            prob_index = sub.get("problem", {}).get("index", "")
            verdict = sub.get("verdict")
            author = sub.get("author", {})
            p_type = author.get("participantType", "")
            
            contests_map[cid]["problems_submitted"].add(prob_index)
            if verdict == "OK":
                contests_map[cid]["problems_solved"].add(prob_index)
                
            current_type = contests_map[cid]["participation_type"]
            if p_type == "CONTESTANT":
                contests_map[cid]["participation_type"] = "REAL"
            elif p_type == "VIRTUAL" and current_type != "REAL":
                contests_map[cid]["participation_type"] = "VIRTUAL"
                
    # 5. Format results
    results = []
    for c in latest_contests:
        c_info = contests_map[c.id]
        c_problems = list(c_info["problems_submitted"])
        
        has_c = any(p == "C" for p in c_info["problems_submitted"])
        has_split = any(p in ["C1", "C2"] for p in c_info["problems_submitted"])
        
        attempted = has_c or has_split
        
        solved = False
        if has_split:
            solved = "C1" in c_info["problems_solved"] and "C2" in c_info["problems_solved"]
        elif has_c:
            solved = "C" in c_info["problems_solved"]
        
        # Determine actual participation type
        part_type = c_info["participation_type"]
        if not c_problems:
            part_type = "UNATTEMPTED"
            
        status = "Not Attempted"
        if solved:
            status = "Upsolved" if not attempted else "Solved"
        elif attempted:
            status = "Attempted but Failed"
            
        results.append({
            "contest_id": c.id,
            "contest_name": c.name,
            "submitted_problems": sorted(c_problems),
            "c_status": status,
            "c_solved": solved,
            "participation_type": part_type
        })
        
    return results

# Serve Frontend static files
frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
