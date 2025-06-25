import os
import sys
import subprocess
from lib import get_db_connection, create_user, hash_password
from textual.app import App, ComposeResult
from textual.widgets import Input, Static, Button, OptionList
from textual.containers import Vertical
from textual.screen import Screen

def run_loader(password=None, resume=False):
    args = ["python3", "loader.py"]
    if resume:
        args.append("--resume")
    env = os.environ.copy()
    if password:
        env["USER_PASSWORD"] = password
    result = subprocess.run(args, env=env)
    return result.returncode

class Login(Vertical):
    def __init__(self, username: str, error: str = ""):
        super().__init__()
        self.username = username
        self.error = error

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static("Login", id="title")
            yield Static(f"Username: {self.username}", id="username-display")
            border_color = "red" if self.error else "white"
            yield Input(placeholder="Password", password=True, id="password", classes=border_color)
            yield Button("Login", id="login-btn")
            if self.error:
                yield Static(self.error, id="login-error", classes="error")

class UserCreate(Vertical):
    """User creation widget."""
    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Static("Create First User", id="title")
            yield Input(placeholder="Username", id="new-username")
            yield Input(placeholder="Password", password=True, id="new-password")
            yield Button("Create User", id="create-user-btn")

class LoginScreen(Screen):
    CSS_PATH = "style.tcss"
    def __init__(self, username: str, error: str = ""):
        super().__init__()
        self.username = username
        self.error = error

    def compose(self) -> ComposeResult:
        yield Login(self.username, self.error)

class UserCreateScreen(Screen):
    CSS_PATH = "style.tcss"
    def compose(self) -> ComposeResult:
        yield UserCreate()

def is_application_running() -> bool:
    try:
        output = subprocess.check_output(["pgrep", "-f", "log.py"])
        return bool(output.strip())
    except subprocess.CalledProcessError:
        return False

def stop_application():
    try:
        subprocess.run(["pkill", "-f", "log.py"], check=True)
    except Exception:
        pass

class AppRunningScreen(Screen):
    CSS_PATH = "style.tcss"
    def compose(self) -> ComposeResult:
        with Vertical(id="app-running-box"):
            yield Static("Application is already running.", id="running-title")
            yield Static("Do you want to continue or restart the application?", id="running-msg")
            with Vertical(id="button-box"):
                yield Button("Continue", id="continue-btn")
                yield Button("Restart", id="restart-btn")

class SecureApp(App):
    CSS = ""

    async def on_mount(self):
        if is_application_running():
            self.push_screen(AppRunningScreen())
            return
        code = run_loader()
        if code == 11:
            self.push_screen(UserCreateScreen())
        elif code == 12:
            username = self.get_username()
            self.push_screen(LoginScreen(username))
        elif code == 0:
            username = self.get_username()
            self.push_screen(LoginScreen(username))
        else:
            print("❌ Loader failed.")
            sys.exit(1)

    def user_exists(self) -> bool:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM users")
                    count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            print(f"[ERROR] DB check failed: {e}")
            return False

    def get_username(self) -> str:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT username FROM users LIMIT 1")
                    row = cursor.fetchone()
            return row[0] if row else ""
        except Exception as e:
            print(f"[ERROR] Failed to get username: {e}")
            return ""

    async def on_button_pressed(self, event):
        button_id = event.button.id
        screen = self.screen_stack[-1]

        if button_id == "create-user-btn":
            username = screen.query_one("#new-username", Input).value
            password = screen.query_one("#new-password", Input).value
            if username and password:
                try:
                    create_user(username, password)
                    print("\n✅ User created successfully. Resuming loader...")
                    await self.action_quit()
                    code = run_loader(resume=True)
                    if code == 0:
                        username = self.get_username()
                        SecureApp().push_screen(LoginScreen(username))
                        sys.exit(0)
                    else:
                        print("❌ Loader failed after user creation.")
                        sys.exit(1)
                except Exception as e:
                    print(f"\n❌ Error creating user: {e}")
            else:
                print("\n❌ Username and password required.")

        elif button_id == "login-btn":
            username = self.get_username()
            password = screen.query_one("#password", Input).value
            if password:
                if await self.verify_password(username, password):
                    print("✅ Login successful. Starting application service...")
                    await self.action_quit()
                    os.environ["USER_PASSWORD"] = password
                    code = run_loader(resume=True, password=password)
                    if code == 0:
                        print("✅ Application started. Opening log viewer...")
                        os.execvp("uv", ["uv", "run", "eye_view.py"])
                    else:
                        print("❌ Loader failed after login.")
                        sys.exit(1)
                else:
                    self.pop_screen()
                    self.push_screen(LoginScreen(username, error="❌ Wrong password!"))
            else:
                self.pop_screen()
                self.push_screen(LoginScreen(username, error="❌ Password required."))

        elif button_id == "continue-btn":
            os.execvp("uv", ["uv", "run", "eye_view.py"])

        elif button_id == "restart-btn":
            stop_application()
            code = run_loader(resume=True)
            if code == 0:
                username = self.get_username()
                self.push_screen(LoginScreen(username))
            else:
                print("❌ Loader failed after restart.")
                sys.exit(1)

    async def verify_password(self, username: str, password: str) -> bool:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
                    row = cursor.fetchone()
            if not row:
                return False
            stored_hash = row[0]
            return stored_hash == hash_password(password)
        except Exception as e:
            print(f"[ERROR] Password verification failed: {e}")
            return False

if __name__ == "__main__":
    SecureApp().run()