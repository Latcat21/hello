import os
from pathlib import Path
import re
import sqlite3
import threading
import datetime as dt
from uuid import uuid4
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, request, session, send_from_directory, g, redirect, abort
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
_env_secret = os.environ.get("SECRET_KEY")
if not _env_secret:
  raise RuntimeError("SECRET_KEY environment variable is required")
app.config["SECRET_KEY"] = _env_secret
UPLOAD_DIR = BASE_DIR / "uploads"
ADMIN_USERS = {"brianlattner.com", "brianlattner@gmail.com"}
ADMIN_USERS_LOWER = {u.lower() for u in ADMIN_USERS}
CHICAGO_TZ = ZoneInfo("America/Chicago")
_scheduler_started = False
_scheduler_lock = threading.Lock()
_last_clear_slot = None

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PASSWORD_PATTERN = re.compile(r"^(?=.*\d).{8,}$")


def get_db():
  if "db" not in g:
    g.db = sqlite3.connect(DB_PATH)
    g.db.row_factory = sqlite3.Row
  return g.db


def close_db(_=None):
  db = g.pop("db", None)
  if db is not None:
    db.close()


def init_db():
  db = get_db()
  db.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      note TEXT DEFAULT ''
    )
    """
  )
  db.execute(
    """
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      body TEXT NOT NULL,
      image_url TEXT,
      link_url TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
  )
  # Add columns if upgrading existing DB
  try:
    db.execute("ALTER TABLE messages ADD COLUMN image_url TEXT")
  except sqlite3.OperationalError:
    pass
  try:
    db.execute("ALTER TABLE messages ADD COLUMN link_url TEXT")
  except sqlite3.OperationalError:
    pass
  db.commit()
  UPLOAD_DIR.mkdir(exist_ok=True)


def allowed_file(filename: str) -> bool:
  return Path(filename).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _remove_uploaded(image_url: str | None):
  if not image_url:
    return
  try:
    path_part = image_url[1:] if image_url.startswith("/") else image_url
    candidate = BASE_DIR / path_part
    if candidate.is_file() and candidate.resolve().is_relative_to(UPLOAD_DIR):
      candidate.unlink()
  except Exception:
    pass


def is_admin(username=None):
  user = username or session.get("user")
  if not user:
    return False
  return user.lower() in ADMIN_USERS_LOWER


def require_admin():
  if not is_admin():
    abort(403)


def validate_username(value: str) -> str:
  value = (value or "").strip()
  if not EMAIL_PATTERN.match(value):
    abort(400, description="Invalid email format.")
  return value.lower()


def validate_password(value: str) -> str:
  value = value or ""
  if not PASSWORD_PATTERN.match(value):
    abort(400, description="Password must be at least 8 characters and include a number.")
  return value


@app.before_request
def ensure_db():
  init_db()
  start_scheduler_once()
  _maybe_clear_now()


@app.teardown_appcontext
def teardown_db(exception):
  close_db(exception)


def current_user():
  username = session.get("user")
  if not username:
    return None
  db = get_db()
  row = db.execute(
    "SELECT username, note FROM users WHERE username = ?", (username,)
  ).fetchone()
  if not row:
    return None
  last_msg = db.execute(
    "SELECT body FROM messages WHERE username = ? ORDER BY created_at DESC LIMIT 1",
    (username,),
  ).fetchone()
  note_value = row["note"] or (last_msg["body"] if last_msg else "")
  return {"username": row["username"], "note": note_value, "is_admin": is_admin(username)}


@app.route("/")
def index():
  return send_from_directory(app.static_folder, "index.html")


@app.route("/auth")
@app.route("/auth/")
def auth_page():
  return send_from_directory(app.static_folder, "auth.html")


@app.route("/signup")
@app.route("/signup/")
def signup_page():
  return send_from_directory(app.static_folder, "signup.html")


@app.route("/account")
@app.route("/account/")
def account_page():
  if "user" not in session:
    return redirect("/auth")
  return send_from_directory(app.static_folder, "account.html")


@app.route("/admin")
@app.route("/admin/")
def admin_page():
  require_admin()
  return send_from_directory(app.static_folder, "admin.html")


@app.route("/chat")
@app.route("/chat/")
def chat_page():
  if "user" not in session:
    return redirect("/auth")
  return send_from_directory(app.static_folder, "chat.html")


@app.route("/preview")
@app.route("/preview/")
def preview_page():
  return send_from_directory(app.static_folder, "preview.html")


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
  return send_from_directory(UPLOAD_DIR, filename)


@app.get("/api/me")
def me():
  user = current_user()
  if not user:
    return jsonify({"authenticated": False})
  return jsonify({"authenticated": True, "user": {"username": user["username"], "is_admin": user.get("is_admin", False)}, "note": user.get("note", "")})


@app.get("/api/notes")
def all_notes():
  if "user" not in session:
    return jsonify({"error": "You must be signed in to view notes."}), 401
  db = get_db()
  rows = db.execute(
    "SELECT id, username, body AS note, image_url, link_url, created_at FROM messages ORDER BY created_at DESC"
  ).fetchall()
  items = [
    {
      "id": row["id"],
      "username": row["username"],
      "note": row["note"] or "",
      "image_url": row["image_url"],
      "link_url": row["link_url"],
      "created_at": row["created_at"],
    }
    for row in rows
  ]
  return jsonify({"notes": items})


@app.post("/api/signup")
def signup():
  data = request.get_json() or {}
  username = validate_username(data.get("username"))
  password = validate_password(data.get("password"))
  if not username or not password:
    return jsonify({"error": "Username and password required."}), 400
  db = get_db()
  try:
    db.execute(
      "INSERT INTO users (username, password, note) VALUES (?, ?, ?)",
      (username, generate_password_hash(password), ""),
    )
    db.commit()
  except sqlite3.IntegrityError:
    return jsonify({"error": "User already exists."}), 400

  session["user"] = username
  return jsonify({"user": {"username": username, "is_admin": is_admin(username)}, "note": ""})


@app.post("/api/login")
def login():
  data = request.get_json() or {}
  username = validate_username(data.get("username"))
  password = data.get("password") or ""
  db = get_db()
  row = db.execute(
    "SELECT username, password, note FROM users WHERE username = ?", (username,)
  ).fetchone()
  if not row or not check_password_hash(row["password"], password):
    return jsonify({"error": "Invalid credentials."}), 400
  session["user"] = username
  return jsonify({"user": {"username": username, "is_admin": is_admin(username)}, "note": row["note"] or ""})


@app.post("/api/logout")
def logout():
  session.pop("user", None)
  return jsonify({"ok": True})


@app.post("/api/note")
def save_note():
  user = session.get("user")
  if not user:
    return jsonify({"error": "You must be signed in to save a note."}), 401
  if not _chat_window_open():
    return jsonify({"error": "Chat is closed. Notes can be posted between 9am and 9pm."}), 403
  data = request.get_json() or {}
  note = data.get("note", "")
  image_url = data.get("image_url") or None
  link_url = data.get("link_url") or None
  db = get_db()
  db.execute(
    "INSERT INTO messages (username, body, image_url, link_url) VALUES (?, ?, ?, ?)",
    (user, note, image_url, link_url),
  )
  db.execute("UPDATE users SET note = ? WHERE username = ?", (note, user))
  db.commit()
  return jsonify({"ok": True})


@app.post("/api/messages/delete")
def delete_messages():
  user = session.get("user")
  if not user:
    return jsonify({"error": "You must be signed in to delete messages."}), 401
  db = get_db()
  images = db.execute(
    "SELECT image_url FROM messages WHERE username = ? AND image_url IS NOT NULL",
    (user,),
  ).fetchall()
  for row in images:
    _remove_uploaded(row["image_url"])
  db.execute("DELETE FROM messages WHERE username = ?", (user,))
  db.execute("UPDATE users SET note = '' WHERE username = ?", (user,))
  db.commit()
  return jsonify({"ok": True})


@app.post("/api/messages/delete_one")
def delete_one_message():
  user = session.get("user")
  if not user:
    return jsonify({"error": "You must be signed in to delete messages."}), 401
  data = request.get_json() or {}
  try:
    msg_id = int(data.get("id", 0))
  except (TypeError, ValueError):
    return jsonify({"error": "Invalid message id."}), 400

  db = get_db()
  row = db.execute(
    "SELECT image_url FROM messages WHERE id = ? AND username = ?",
    (msg_id, user),
  ).fetchone()
  cur = db.execute(
    "DELETE FROM messages WHERE id = ? AND username = ?", (msg_id, user)
  )
  db.commit()
  if cur.rowcount == 0:
    return jsonify({"error": "Message not found or not yours."}), 404
  if row:
    _remove_uploaded(row["image_url"])
  return jsonify({"ok": True})


def _delete_user_and_data(username: str):
  db = get_db()
  images = db.execute(
    "SELECT image_url FROM messages WHERE username = ? AND image_url IS NOT NULL",
    (username,),
  ).fetchall()
  for row in images:
    _remove_uploaded(row["image_url"])
  db.execute("DELETE FROM messages WHERE username = ?", (username,))
  db.execute("DELETE FROM users WHERE username = ?", (username,))
  db.commit()


@app.get("/api/admin/users")
def admin_users():
  require_admin()
  db = get_db()
  rows = db.execute("SELECT username, note FROM users ORDER BY username").fetchall()
  return jsonify(
    {
      "users": [
        {"username": r["username"], "note": r["note"], "is_admin": is_admin(r["username"])}
        for r in rows
      ]
    }
  )


@app.post("/api/admin/users/delete")
def admin_delete_user():
  require_admin()
  data = request.get_json() or {}
  username = validate_username(data.get("username"))
  if not username:
    return jsonify({"error": "Username required"}), 400
  if username in ADMIN_USERS:
    return jsonify({"error": "Cannot delete admin user."}), 400
  if username == session.get("user"):
    return jsonify({"error": "You cannot delete your own admin session."}), 400
  _delete_user_and_data(username)
  return jsonify({"ok": True})


@app.post("/api/upload_image")
def upload_image():
  user = session.get("user")
  if not user:
    return jsonify({"error": "You must be signed in to upload images."}), 401
  file = request.files.get("file")
  if not file or not file.filename:
    return jsonify({"error": "No file provided."}), 400
  filename = secure_filename(file.filename)
  if not allowed_file(filename):
    return jsonify({"error": "Unsupported file type."}), 400
  ext = Path(filename).suffix.lower()
  final_name = f"{uuid4().hex}{ext}"
  save_path = UPLOAD_DIR / final_name
  file.save(save_path)
  return jsonify({"url": f"/uploads/{final_name}"})


def clear_all_messages():
  with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
      "SELECT image_url FROM messages WHERE image_url IS NOT NULL"
    ).fetchall()
    for row in rows:
      _remove_uploaded(row["image_url"])
    conn.execute("DELETE FROM messages")
    conn.execute("UPDATE users SET note = ''")
    conn.commit()


def _seconds_until_next_clear(now=None):
  now = now or dt.datetime.now(CHICAGO_TZ)
  today = now.date()
  targets = [
    dt.datetime.combine(today, dt.time(hour=9), tzinfo=CHICAGO_TZ),
    dt.datetime.combine(today, dt.time(hour=21), tzinfo=CHICAGO_TZ),
  ]
  future_targets = [t for t in targets if t > now]
  next_target = future_targets[0] if future_targets else dt.datetime.combine(
    today + dt.timedelta(days=1), dt.time(hour=9), tzinfo=CHICAGO_TZ
  )
  delta = (next_target - now).total_seconds()
  return max(5, delta)


def _chat_window_open(now=None):
  now = now or dt.datetime.now(CHICAGO_TZ)
  return 9 <= now.hour < 21


def _current_slot(now=None):
  now = now or dt.datetime.now(CHICAGO_TZ)
  if now.hour < 9:
    return f"{now.date()}-pre9"
  if now.hour < 21:
    return f"{now.date()}-day"
  return f"{now.date()}-post21"


def _schedule_clears():
  def run_and_reschedule():
    clear_all_messages()
    threading.Timer(_seconds_until_next_clear(), run_and_reschedule).start()

  threading.Timer(_seconds_until_next_clear(), run_and_reschedule).start()


def _maybe_clear_now():
  global _last_clear_slot
  now = dt.datetime.now(CHICAGO_TZ)
  slot = _current_slot(now)
  if slot == _last_clear_slot:
    return
  if not _chat_window_open(now):
    clear_all_messages()
    _last_clear_slot = slot


def start_scheduler_once():
  global _scheduler_started
  with _scheduler_lock:
    if not _scheduler_started:
      _scheduler_started = True
      _schedule_clears()


if __name__ == "__main__":
  app.run(debug=True)
