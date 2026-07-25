import argparse
from scripts.era_scoring import load_peer_summary, PeerIndex, fit_global_xi

parser = argparse.ArgumentParser()
parser.add_argument("--chart", default="hot-100")
parser.add_argument("--peer-summary", default=None)
args = parser.parse_args()

peer_summary_path = args.peer_summary or f"data/processed/{args.chart}_weekly_peer_summary.parquet"
peer_summary = load_peer_summary(peer_summary_path)
peer_index = PeerIndex(peer_summary)

xi_global = fit_global_xi(peer_index)
print(f"\nFinal xi_global for {args.chart}: {xi_global:.4f}")