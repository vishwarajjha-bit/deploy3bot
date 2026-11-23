import sqlite3

DB_NAME = "hosted_bots.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            name TEXT PRIMARY KEY,
            script_path TEXT NOT NULL,
            status TEXT DEFAULT 'stopped',
            pid INTEGER DEFAULT NULL,
            entry_script TEXT DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            role TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("PRAGMA table_info(bots)")
    cols = {row[1] for row in c.fetchall()}
    if "pid" not in cols:
        c.execute("ALTER TABLE bots ADD COLUMN pid INTEGER DEFAULT NULL")
    if "entry_script" not in cols:
        c.execute("ALTER TABLE bots ADD COLUMN entry_script TEXT DEFAULT NULL")
    conn.commit()
    conn.close()


def seed_owners(owner_ids):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for uid in owner_ids:
        c.execute(
            """
            INSERT INTO admins (user_id, added_by, role)
            VALUES (?, ?, 'owner')
            ON CONFLICT(user_id) DO UPDATE SET role = 'owner'
            """,
            (int(uid), int(uid)),
        )
    conn.commit()
    conn.close()


def add_admin(user_id, added_by, role="admin"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO admins (user_id, added_by, role)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET role = excluded.role
        """,
        (int(user_id), int(added_by), role),
    )
    conn.commit()
    conn.close()


def remove_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id = ? AND role != 'owner'", (int(user_id),))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_all_admins():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, added_by, role, created_at FROM admins ORDER BY role DESC, user_id ASC")
    rows = c.fetchall()
    conn.close()
    return rows


def is_authorized(user_id, owner_ids):
    if int(user_id) in {int(x) for x in owner_ids}:
        return True
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (int(user_id),))
    row = c.fetchone()
    conn.close()
    return row is not None


def add_bot(name, script_path, entry_script=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        INSERT OR REPLACE INTO bots (name, script_path, status, pid, entry_script)
        VALUES (?, ?, 'stopped', NULL, ?)
        """,
        (name, script_path, entry_script or script_path),
    )
    conn.commit()
    conn.close()


def get_all_bots():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name, script_path, status, pid, entry_script FROM bots ORDER BY name ASC")
    rows = c.fetchall()
    conn.close()
    return rows


def get_bot(name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name, script_path, status, pid, entry_script FROM bots WHERE name = ?", (name,))
    row = c.fetchone()
    conn.close()
    return row


def update_status(name, status, pid=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE bots SET status = ?, pid = ? WHERE name = ?", (status, pid, name))
    conn.commit()
    conn.close()


def delete_bot_record(name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM bots WHERE name = ?", (name,))
    conn.commit()
    conn.close()
