# leaderboard_utils.py
# ======================
# Handles rank calculation + role naming
# ======================

def assign_rank(xp: int) -> str:
    """Return the rank tier based on XP."""
    tiers = [
        (0, "Bronze I"), (100, "Bronze II"), (200, "Bronze III"),
        (400, "Silver I"), (600, "Silver II"), (800, "Silver III"),
        (1200, "Gold I"), (1600, "Gold II"), (2000, "Gold III"),
        (2600, "Platinum I"), (3200, "Platinum II"), (3800, "Platinum III"),
        (4600, "Diamond I"), (5400, "Diamond II"), (6200, "Diamond III"),
        (7200, "Elite"), (8500, "Champion"), (10000, "Unreal")
    ]
    rank = "Unranked"
    for threshold, role in tiers:
        if xp >= threshold:
            rank = role
    return rank

def get_rank_role(rank: str) -> str:
    """Return role name from rank string (same as rank here)."""
    return rank
