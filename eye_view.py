import sys
import os
import pathlib
import time
from lib import get_db_connection
from lib import derive_aes_key, decrypt_data, hash_password
from textual.app import App, ComposeResult
from textual.widgets import Input, Static, Button, DataTable
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.binding import Binding
from decouple import config

TABLE_NAME = config("TABLE_NAME", default="auth_log")

class LoginScreen(Screen):
    CSS_PATH = "style.tcss"

    def __init__(self, error: str = ""):
        super().__init__()
        self.error = error

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static("Login", id="title")
            yield Input(placeholder="Username", id="username")
            yield Input(placeholder="Password", password=True, id="password")
            yield Button("Login", id="login-btn")
            yield Static(self.error, id="login-error")

class LogViewerScreen(Screen):
    CSS_PATH = "style.tcss"
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    def __init__(self, username, user_key):
        super().__init__()
        self.username = username
        self.user_key = user_key
        self.logs = []
        self.filtered_logs = []
        self.search_term = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Press Ctrl+Q to quit", id="quit-hint")
            yield Static(f"Logged in as: {self.username}", id="user-label")
            with Horizontal():
                yield Input(placeholder="Search logs...", id="searchbox")
            self.table = DataTable(id="log-table")
            yield self.table

    async def on_mount(self):
        self.table.add_columns("ID", "Timestamp", "Hostname", "Service", "Message", "State")
        await self.load_logs()
        self.last_update = pathlib.Path(".log_update").stat().st_mtime if pathlib.Path(".log_update").exists() else 0
        self.set_interval(1, self.check_for_update)

    async def check_for_update(self):
        update_file = pathlib.Path(".log_update")
        if update_file.exists():
            mtime = update_file.stat().st_mtime
            if mtime > getattr(self, "last_update", 0):
                self.last_update = mtime
                await asyncio.sleep(2)  # Debounce: wait for more logs
                await self.load_logs()

    async def refresh_logs(self):
        await self.load_logs()

    async def load_logs(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, timestamp, hostname, service, message, state FROM {TABLE_NAME} ORDER BY id DESC LIMIT 100")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            logs = []
            for row in rows:
                try:
                    id_, ts, enc_host, enc_service, enc_msg, state = row
                    host = decrypt_data(enc_host, self.user_key)
                    service = decrypt_data(enc_service, self.user_key)
                    msg = decrypt_data(enc_msg, self.user_key)
                    logs.append((id_, str(ts), host, service, msg, state))
                except Exception:
                    continue
            self.logs = logs
            self.apply_filter()
        except Exception as e:
            self.query_one("#user-label", Static).update(f"[ERROR] Failed to load logs: {e}")

    def apply_filter(self):
        term = self.search_term.lower()
        if term:
            self.filtered_logs = [
                log for log in self.logs
                if any(term in str(field).lower() for field in log)
            ]
        else:
            self.filtered_logs = self.logs
        self.update_table()

    def update_table(self):
        self.table.clear()
        for log in self.filtered_logs:
            self.table.add_row(*[str(x) for x in log])

    async def on_input_changed(self, event):
        if event.input.id == "searchbox":
            self.search_term = event.value
            self.apply_filter()

    def action_quit(self):
        self.app.exit()

class ErrorScreen(Screen):
    def __init__(self, error_msg):
        super().__init__()
        self.error_msg = error_msg

    def compose(self) -> ComposeResult:
        with Vertical(id="error-box"):
            yield Static("❌ Database Connection Failed", id="error-title")
            yield Static(self.error_msg, id="error-msg")
            yield Button("Exit", id="exit-btn")

    async def on_button_pressed(self, event):
        if event.button.id == "exit-btn":
            sys.exit(1)

class EyeViewerApp(App):
    CSS_PATH = "style.tcss"
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    async def on_mount(self):
        username = None
        password = os.environ.get("USER_PASSWORD")
        # Get first username from DB
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT username, password_hash, kdf_salt FROM users LIMIT 1")
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                username, stored_hash, kdf_salt = row
                if password and stored_hash == hash_password(password):
                    user_key = derive_aes_key(password, kdf_salt)
                    # Remove password from env after use
                    os.environ.pop("USER_PASSWORD", None)
                    self.push_screen(LogViewerScreen(username, user_key))
                    return
        except Exception as e:
            self.push_screen(ErrorScreen(f"Auto-login failed: {e}"))
            return
        # If auto-login fails, fallback to login screen
        self.push_screen(LoginScreen())

    async def on_button_pressed(self, event):
        if event.button.id == "login-btn":
            screen = self.screen_stack[-1]
            username = screen.query_one("#username", Input).value
            password = screen.query_one("#password", Input).value
            error_widget = screen.query_one("#login-error", Static)
            if not username or not password:
                error_widget.update("Username and password required.")
                return
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash, kdf_salt FROM users WHERE username = %s", (username,))
                row = cursor.fetchone()
                cursor.close()
                conn.close()
                if not row:
                    error_widget.update("Invalid username or password.")
                    return
                stored_hash, kdf_salt = row
                if stored_hash != hash_password(password):
                    error_widget.update("Invalid username or password.")
                    return
                user_key = derive_aes_key(password, kdf_salt)
                self.push_screen(LogViewerScreen(username, user_key))
            except Exception as e:
                error_widget.update(f"Login failed: {e}")

    def action_quit(self):
        self.exit()

if __name__ == "__main__":
    EyeViewerApp().run()