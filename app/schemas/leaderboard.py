from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    points: int
    is_you: bool = False


class LeaderboardResponse(BaseModel):
    leaderboard: list[LeaderboardEntry]
