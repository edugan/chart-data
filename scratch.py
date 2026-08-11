import pandas as pd
from scripts.era_scoring import load_peer_summary

ps = load_peer_summary("data/processed/hot-100_weekly_peer_summary_min2.parquet")
total_peers = sum(len(pts) for pts in ps["points_list"])
print(total_peers)