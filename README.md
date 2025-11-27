praciting git with harvard cs50w

## Run the Flask demo

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install flask werkzeug
flask --app app run
```

Then open http://127.0.0.1:5000 in your browser. You can sign up, sign in, and save a note per user (data stored in SQLite).

Auth lives at http://127.0.0.1:5000/auth, and successful sign-in/sign-up will send you back to the main page to use the live feed. Sign up directly at http://127.0.0.1:5000/signup.

Chat room: http://127.0.0.1:5000/chat shows the shared feed and message form with links back home and sign out.
Admin: http://127.0.0.1:5000/admin is restricted to the configured admin user; list and delete users.

### Data storage
- Uses SQLite (`data.db` in the project root) with hashed passwords (Werkzeug).
- Messages are stored in the `messages` table with timestamps; visible to signed-in users only.
- Uploaded images are stored in `uploads/` and referenced in message feed previews.
- To reset data, delete `data.db` and restart the Flask app; tables will be recreated automatically.
