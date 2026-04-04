"""Reset all drones to available and resolve all open incidents."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from db.supabase import supabase

drones = supabase.table("drones").select("id, name").execute().data
for d in drones:
    supabase.table("drones").update({"status": "available"}).eq("id", d["id"]).execute()
    print(f"Reset {d['name']} -> available")

incidents = supabase.table("incidents").select("id, status").execute().data
for i in incidents:
    if i["status"] != "resolved":
        supabase.table("incidents").update({"status": "resolved"}).eq("id", i["id"]).execute()
        print(f"Resolved incident {i['id'][:8]}...")

print("Done")
