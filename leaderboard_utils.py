from database import get_all_users  # or however you're fetching user data

def get_top_kd_players(limit=10):
    users = get_all_users()
    kd_sorted = sorted(users, key=lambda u: u.get('kd', 0), reverse=True)
    return kd_sorted[:limit]