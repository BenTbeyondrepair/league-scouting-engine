import time
import math
import pandas as pd
import numpy as np
from riotwatcher import RiotWatcher, LolWatcher, ApiError

# ==========================================
# 1. SETUP YOUR API KEYS AND REGIONS
# ==========================================
API_KEY = "RGAPI-2da0b96b-72bb-4faf-a5b7-4ad067da0a30"

# We initialize BOTH watchers to access global accounts AND league matches
riot_watcher = RiotWatcher(API_KEY)
lol_watcher = LolWatcher(API_KEY)

# Region settings
MATCH_REGION = 'americas' 
PLATFORM_REGION = 'na1'   

# ==========================================
# 2. DEFINE YOUR LIST OF SUPPORT PLAYERS
# ==========================================
# Type their exact Riot ID and Tagline below. 
# You can add as many as you want following this format:
support_players = [
    {"name": "BenTbeyondrepair", "tag": "NA1"},
    {"name": "Vulcan", "tag": "NA1"},
]

# ==========================================
# 3. THE MATHEMATICAL SLS EQUATION
# ==========================================
def calculate_sls(kp, vspm, deaths):
    numerator = kp * math.log(vspm + 1)
    denominator = 1 + math.exp(0.4 * (deaths - 4))
    return numerator / denominator

# ==========================================
# 4. START THE ROLE-FILTERED TRACKING LOOP
# ==========================================
leaderboard = []

print("🚀 Starting Role-Filtered SLS Engine (Targeting last 50 ON-ROLE Solo Q games)...\n")

for player in support_players:
    game_name = player["name"]
    tag_line = player["tag"]
    print(f"Retrieving profile for {game_name}#{tag_line}...")
    
    try:
        # Convert Riot ID to PUUID
        account_data = riot_watcher.account.by_riot_id(MATCH_REGION, game_name, tag_line)
        puuid = account_data['puuid']
        
        # Pull a larger initial batch (100 matches) to ensure we find 50 pure support games
        # queue=420 explicitly filters out Normal, Flex, ARAM, and Clash games automatically
        match_ids = lol_watcher.match.matchlist_by_puuid(
            MATCH_REGION, puuid, count=100, queue=420
        )
        
        player_sls_scores = []
        valid_games_counted = 0
        
        print(f"-> Scanning matches for {game_name} (Filtering for UTILITY role)...")
        for match_id in match_ids:
            # Stop once we have compiled exactly 50 pure support games
            if valid_games_counted >= 50:
                break
                
            match_detail = lol_watcher.match.by_id(MATCH_REGION, match_id)
            info = match_detail['info']
            
            # Identify the target player
            target_participant = None
            allied_team_id = None
            total_team_kills = 0
            
            for p in info['participants']:
                if p['puuid'] == puuid:
                    target_participant = p
                    allied_team_id = p['teamId']
                    break
            
            # Core Filters: Skip if player disconnected, game was a remake, or role wasn't Support
            if not target_participant or info['gameDuration'] < 300:
                continue
            
            # Riot maps the Support role specifically to the 'UTILITY' system string
            if target_participant.get('individualPosition') != 'UTILITY':
                continue # Discards off-role/autofill games seamlessly
                
            # Accumulate total team kills for accurate Kill Participation
            for p in info['participants']:
                if p['teamId'] == allied_team_id:
                    total_team_kills += p['kills']
            
            # Extract metrics
            kills = target_participant['kills']
            assists = target_participant['assists']
            deaths = target_participant['deaths']
            vision_score = target_participant['visionScore']
            game_minutes = info['gameDuration'] / 60.0
            
            # Calculate engineered metrics
            vspm = vision_score / game_minutes
            kp = (kills + assists) / total_team_kills if total_team_kills > 0 else 0.0
            
            # Compute SLS and increment count
            game_sls = calculate_sls(kp, vspm, deaths)
            player_sls_scores = np.append(player_sls_scores, game_sls)
            valid_games_counted += 1
            
        # Compile final scoreboard averages
        if len(player_sls_scores) > 0:
            avg_sls = np.mean(player_sls_scores)
            leaderboard.append({
                "Player": f"{game_name}#{tag_line}",
                "Pure_Support_Games": len(player_sls_scores),
                "Average_SLS": round(avg_sls, 4)
            })
            print(f"✅ Finished {game_name}. Parsed {len(player_sls_scores)} on-role games. Avg SLS: {round(avg_sls, 4)}")
        else:
            print(f"⚠️ No valid UTILITY Solo Queue games found for {game_name} in recent match history.")
            
    except ApiError as err:
        if err.response.status_code == 404:
            print(f"❌ Player {game_name}#{tag_line} not found.")
        elif err.response.status_code == 403:
            print("❌ API Key Expired or Invalid! Grab a fresh copy from Riot's site.")
            break
        else:
            print(f"❌ API Error: {err}")

# ==========================================
# 5. DISPLAY THE SCOUTING LEADERBOARD
# ==========================================
print("\n=== UPCOMING TALENT RANKINGS: SUPPORT POSITION (BY SLS) ===")
leaderboard_df = pd.DataFrame(leaderboard)
if not leaderboard_df.empty:
    leaderboard_df = leaderboard_df.sort_values(by="Average_SLS", ascending=False)
    print(leaderboard_df.to_string(index=False))
else:
    print("No data successfully processed.")
