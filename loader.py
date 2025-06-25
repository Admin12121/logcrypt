import os
import sys
import time
import shutil
import termios
import tty
import subprocess
import json
from lib import get_db_connection

RED = "\033[91m"
BLUE = "\033[94m"
WHITE = "\033[97m"
RESET = "\033[0m"
CURSOR_BLOCK = "\u2588"
TEXT = ">_ vicky"

MAX_LOG_WIDTH = 45
LOG_PADDING = 4
LOG_LINES_DISPLAYED = 10
SERVICE_START_DELAY = 0.5
LOADER_END_DELAY = 2

SERVICES = [
    {
        "name": "mariadb",
        "check": "mariadbd",
        "start": ["service", "mariadb", "start"]
    },
    {
        "name": "rsyslogd",
        "check": "rsyslogd",
        "start": ["rsyslogd"]
    },
    {
        "name": "ssh",
        "check": "sshd",
        "start": ["/usr/sbin/sshd"]
    },
    {
        "name": "application",
        "check": "log.py",
        "start": ["/app/start.sh"]
    }
]

APP_LOG_PATH = "/var/log/app.log"
APP_CWD = "/app"
LOADER_STATE_FILE = "loader_state.json"

def hide_cursor():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

def show_cursor():
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()

def move_cursor(row, col):
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()

def clear_line():
    sys.stdout.write("\033[2K")
    sys.stdout.flush()

def clear_screen():
    sys.stdout.write("\033[2J")
    sys.stdout.flush()

def get_log_color(msg: str) -> str:
    msg_lower = msg.lower()
    if "❌" in msg or "fail" in msg_lower or "error" in msg_lower:
        return RED
    elif "✅" in msg or "started" in msg_lower or "running" in msg_lower or "ok" in msg_lower:
        return BLUE
    return WHITE

def is_process_running(name: str) -> bool:
    try:
        output = subprocess.check_output(["pgrep", "-f", name])
        return bool(output.strip())
    except subprocess.CalledProcessError:
        return False

def start_service(command: list) -> bool:
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        with open(APP_LOG_PATH, "a") as log_file:
            log_file.write(f"Failed to start service {command}: {e}\n")
        return False

def user_exists(conn):
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
    return count > 0

def display_logs(logs, width, height, log_col):
    log_lines = logs[-LOG_LINES_DISPLAYED:]
    for i, log in enumerate(reversed(log_lines)):
        row = height - i - 1
        move_cursor(row, log_col)
        clear_line()
        sys.stdout.write(f"{get_log_color(log)}{log.ljust(MAX_LOG_WIDTH)[:MAX_LOG_WIDTH]}{RESET}")
    sys.stdout.flush()

def save_loader_state(logs, service_index):
    state = {
        "logs": logs,
        "service_index": service_index
    }
    with open(LOADER_STATE_FILE, "w") as f:
        json.dump(state, f)

def load_loader_state():
    if os.path.exists(LOADER_STATE_FILE):
        with open(LOADER_STATE_FILE, "r") as f:
            state = json.load(f)
        os.remove(LOADER_STATE_FILE)
        return state.get("logs", []), state.get("service_index", 0)
    return [], 0

def loader():
    size = shutil.get_terminal_size()
    width, height = size.columns, size.lines
    center_line = height // 2
    center_col = (width - len(TEXT) - 1) // 2
    log_col = max(1, width - MAX_LOG_WIDTH - LOG_PADDING)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)

    logs, service_index = [], 0
    warnings = []
    if "--resume" in sys.argv:
        logs, service_index = load_loader_state()

    visible = True
    hide_cursor()
    clear_screen()

    try:
        loading_done = False

        while service_index < len(SERVICES):
            move_cursor(center_line, center_col)
            clear_line()
            cursor = f"{RED}{CURSOR_BLOCK}{RESET}" if visible else " "
            sys.stdout.write(f"{WHITE}{TEXT}{RESET} {cursor}")
            visible = not visible

            service = SERVICES[service_index]
            name = service["name"]

            logs.append(f"Checking {name}..........")
            display_logs(logs, width, height, log_col)
            time.sleep(SERVICE_START_DELAY)

            running = is_process_running(service["check"])

            if running:
                logs.append(f"{name} is already running..........")
                display_logs(logs, width, height, log_col)
                time.sleep(SERVICE_START_DELAY)
            else:
                logs.append(f"{name} not running..........")
                display_logs(logs, width, height, log_col)
                time.sleep(SERVICE_START_DELAY)

                if name == "application":
                    if "--resume" not in sys.argv:
                        logs.append("🔒 Awaiting user login before starting application service...")
                        display_logs(logs, width, height, log_col)
                        save_loader_state(logs, service_index)
                        time.sleep(SERVICE_START_DELAY)
                        sys.exit(12)

                logs.append(f"Starting service {name}..........")
                display_logs(logs, width, height, log_col)
                time.sleep(SERVICE_START_DELAY)

                result = start_service(service["start"])
                if result:
                    logs.append(f"Service {name} started..........")
                else:
                    error_msg = f"❌ Failed to start {name}."
                    logs.append(error_msg)
                    warnings.append(error_msg)
                display_logs(logs, width, height, log_col)
                time.sleep(SERVICE_START_DELAY)

            if name == "mariadb":
                logs.append("Checking database connection..........")
                display_logs(logs, width, height, log_col)
                time.sleep(SERVICE_START_DELAY)
                try:
                    with get_db_connection() as conn:
                        logs.append("✅ Database connection established..........")
                        display_logs(logs, width, height, log_col)
                        time.sleep(SERVICE_START_DELAY)

                        if not user_exists(conn):
                            warn_msg = "❌ No user found. Please create a user in the UI."
                            logs.append(warn_msg)
                            warnings.append(warn_msg)
                            display_logs(logs, width, height, log_col)
                            save_loader_state(logs, service_index)
                            time.sleep(SERVICE_START_DELAY)
                            sys.exit(11)
                        else:
                            logs.append("User exists. Continuing startup..........")
                            display_logs(logs, width, height, log_col)
                            time.sleep(SERVICE_START_DELAY)
                except Exception as e:
                    warn_msg = f"❌ Database connection failed: {e}"
                    logs.append(warn_msg)
                    warnings.append(warn_msg)
                    display_logs(logs, width, height, log_col)
                    time.sleep(SERVICE_START_DELAY)

            service_index += 1
            display_logs(logs, width, height, log_col)
            time.sleep(0.3)

        # All services done
        time.sleep(LOADER_END_DELAY)

        if warnings:
            move_cursor(center_line + 2, 1)
            print(f"{RED}Warnings during startup:{RESET}")
            for w in warnings:
                print(f"{RED}- {w}{RESET}")

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        show_cursor()
        clear_screen()
        move_cursor(0, 0)

if __name__ == "__main__":
    loader()