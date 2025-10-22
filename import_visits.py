import sys, csv, sqlite3
DB = "data.db"
def db(): return sqlite3.connect(DB)
def main(path):
    with open(path, newline="", encoding="utf-8") as f, db() as conn:
        reader = csv.DictReader(f)
        for row in reader:
            chat_id = int(row["chat_id"])
            bill_id = row["bill_id"]
            visited_at = row.get("visited_at") or ""
            conn.execute("INSERT INTO visits(chat_id, bill_id, visited_at) VALUES (?,?,?)",
                         (chat_id, bill_id, visited_at))
        conn.commit()
    print("Imported", path)
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_visits.py visits.csv")
    else:
        main(sys.argv[1])
