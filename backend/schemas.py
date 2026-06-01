from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserProfileResponse(BaseModel):
    cf_handle: str
    current_rating: int
    max_rating: int
    last_fetched: datetime

    class Config:
        orm_mode = True

class DailyStatsResponse(BaseModel):
    handle: str
    date: str
    accepted_count: int
    average_difficulty: float

    class Config:
        orm_mode = True

class ProblemLogCreate(BaseModel):
    handle: str
    problem_id: str
    problem_title: str
    rating: Optional[int] = None
    status: str # 'AC', 'FAILED', 'UP_SOLVING'
    mistake_category: Optional[str] = None
    custom_notes: Optional[str] = None
    solved_date: str

class ProblemLogResponse(BaseModel):
    id: int
    handle: str
    problem_id: str
    problem_title: str
    rating: Optional[int]
    status: str
    mistake_category: Optional[str]
    custom_notes: Optional[str]
    solved_date: str
    created_at: datetime

    class Config:
        orm_mode = True

class DashboardResponse(BaseModel):
    cf_handle: str
    rating: int
    rank: str
    accepted_today: int
    average_difficulty_today: float
    recent_submissions: List[dict]
