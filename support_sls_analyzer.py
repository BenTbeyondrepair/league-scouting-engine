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
# 4. START THE TRACKING LOOP
# ==========================================
leaderboard = []

print("🚀 Starting SLS Analysis Engine for Last 50 Solo Queue Games...\n")

for player in support_players:
    game_name = player["name"]
    tag_line = player["tag"]
    print(f"Retrieving profile for {game_name}#{tag_line}...")
    
    try:
        # Convert Riot ID to unique system ID (PUUID)
        account_data = riot_watcher.account.by_riot_id(MATCH_REGION, game_name, tag_line)
        puuid = account_data['puuid']
        
          # Fetch last 50 Ranked Solo Queue match IDs (Queue ID 420 = Solo Q)
        match_ids = lol_watcher.match.matchlist_by_puuid(
            MATCH_REGION, puuid, count=50, queue=420
        )
        
        player_sls_scores = []
        
        print(f"-> Processing 50 matches for {game_name} (Rate limiting active)...")
        for match_id in match_ids:
            # Sleep 1.2 seconds to prevent crashing a free Riot developer key limit
            time.sleep(1.2) 
            
            match_detail = lol_watcher.match.by_id(MATCH_REGION, match_id)
            info = match_detail['info']
            
            # Find the target player's stats and their team's total kills
            target_participant = None
            allied_team_id = None
            total_team_kills = 0
            
            for p in info['participants']:
                if p['puuid'] == puuid:
                    target_participant = p
                    allied_team_id = p['teamId']
                    break
            
            # Skip games if player didn't load or game was an early remake
            if not target_participant or info['gameDuration'] < 300:
                continue
                
            # Aggregate total team kills for Kill Participation
            for p in info['participants']:
                if p['teamId'] == allied_team_id:
                    total_team_kills += p['kills']
            
            # Extract numbers
            kills = target_participant['kills']
            assists = target_participant['assists']
            deaths = target_participant['deaths']
            vision_score = target_participant['visionScore']
            game_minutes = info['gameDuration'] / 60.0
            
            # Process metrics
            vspm = vision_score / game_minutes
            kp = (kills + assists) / total_team_kills if total_team_kills > 0 else 0.0
            
            # Compute SLS for this game
            game_sls = calculate_sls(kp, vspm, deaths)
            player_sls_scores = np.append(player_sls_scores, game_sls)
            
        # Calculate final average for this player
        if len(player_sls_scores) > 0:
            avg_sls = np.mean(player_sls_scores)
            leaderboard.append({
                "Player": f"{game_name}#{tag_line}",
                "Games_Analyzed": len(player_sls_scores),
                "Average_SLS": round(avg_sls, 4)
            })
            print(f"✅ Finished {game_name}. Avg SLS: {round(avg_sls, 4)}")
        else:
            print(f"⚠️ No valid Solo Queue games found for {game_name}.")
            
    except ApiError as err:
        if err.response.status_code == 404:
            print(f"❌ Player {game_name}#{tag_line} not found.")
        elif err.response.status_code == 403:
            print("❌ API Key Expired or Invalid! Go grab a fresh one from Riot.")
            break
        else:
            print(f"❌ API Error: {err}")

# ==========================================
# 5. DISPLAY THE TALENT RANKING
# ==========================================
print("\n=== FINAL SUPPORT PROSPECT RANKINGS (BY SLS) ===")
leaderboard_df = pd.DataFrame(leaderboard)
if not leaderboard_df.empty:
    leaderboard_df = leaderboard_df.sort_values(by="Average_SLS", ascending=False)
    print(leaderboard_df.to_string(index=False))
else:
    print("No data successfully processed.")
