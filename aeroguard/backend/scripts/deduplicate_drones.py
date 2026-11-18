"""
Deduplicate drones in Supabase database.
Keeps 1 drone per name, reassigns dispatch_logs, and deletes duplicates.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from db.supabase import supabase

def main():
    drones = supabase.table("drones").select("*").order("name").execute().data
    seen = {}
    duplicates_to_delete = []
    reassign_map = {}

    for d in drones:
        name = d["name"]
        if name not in seen:
            seen[name] = d["id"]
        else:
            duplicates_to_delete.append(d["id"])
            reassign_map[d["id"]] = seen[name]

    if not duplicates_to_delete:
        print("No duplicate drones found! Database is already clean.")
        return

    # 1. Update dispatch_logs referencing duplicate IDs
    for old_id, new_id in reassign_map.items():
        supabase.table("dispatch_logs").update({"drone_id": new_id}).eq("drone_id", old_id).execute()
        print(f"Reassigned dispatch_logs: {old_id} -> {new_id}")

    # 2. Delete duplicate drones
    for old_id in duplicates_to_delete:
        supabase.table("drones").delete().eq("id", old_id).execute()
        print(f"Deleted duplicate drone: {old_id}")

    # 3. Verify
    remaining = supabase.table("drones").select("id, name, status, battery_pct").execute().data
    print(f"\nClean! Remaining drones count: {len(remaining)}")
    for r in remaining:
        print(f" - {r['name']}: {r['status']} ({r['battery_pct']}%)")

if __name__ == "__main__":
    main()
