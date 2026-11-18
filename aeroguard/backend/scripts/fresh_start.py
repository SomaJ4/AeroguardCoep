"""Clear all dispatch logs, reset drones to home, resolve all incidents."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
from db.supabase import supabase

# 1. Delete ALL dispatch logs
logs = supabase.table("dispatch_logs").select("id").execute().data
for l in logs:
    supabase.table("dispatch_logs").delete().eq("id", l["id"]).execute()
print(f"Deleted {len(logs)} dispatch logs")

# 2. Reset all drones to available at home position
drones = supabase.table("drones").select("id, name, home_lat, home_lng").execute().data
for d in drones:
    supabase.table("drones").update({
        "status": "available",
        "lat": d["home_lat"],
        "lng": d["home_lng"]
    }).eq("id", d["id"]).execute()
    print("Reset " + d["name"] + " -> available at home")

# 3. Resolve all open incidents
incidents = supabase.table("incidents").select("id, status").execute().data
resolved = 0
for i in incidents:
    if i["status"] != "resolved":
        supabase.table("incidents").update({"status": "resolved"}).eq("id", i["id"]).execute()
        resolved += 1
print(f"Resolved {resolved} incidents")
print("Database is fresh!")
