import os
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import mysql.connector
from lib import derive_aes_key, encrypt_data
from decouple import config
import pathlib

LOG_FILE = "/var/log/auth.log"
DB_CONFIG = {
    "host": "localhost",
    "user": config("DB_USER", default="grooot"),
    "password": config("DB_PASS", default="grooot"),
    "database": config("DB_NAME", default="grooot"),
}

TABLE_NAME = config("TABLE_NAME", default="auth_log")

STATE_MAP = {
    'Accepted password': 'success',
    'session opened': 'success',
    'password changed': 'success',
    'Failed password': 'failed',
    'authentication failure': 'failed',
    'error': 'error',
    'Failed to connect': 'error',
    'Cannot bind': 'error',
    'logout() returned an error': 'error',
    'disconnect': 'failed',
    'disconnected by user': 'failed',
    'session closed': 'success',
    'unable to open env file': 'error',
    'starting session': 'success',
    'connection from': 'success'
}

def parse_log_line(line):
    try:
        parts = line.strip().split(' ', 3)
        ts = datetime.fromisoformat(parts[0])
        host = parts[1]
        service, msg = parts[2].split(':', 1)
        msg = parts[3] if len(parts) > 3 else ""
        return ts, host, service.strip(), msg.strip()
    except Exception as e:
        print(f"[ERROR] Failed to parse line: {line.strip()} - {e}")
        return None

def get_state(msg):
    for key, state in STATE_MAP.items():
        if key.lower() in msg.lower():
            return state
    return "unknown"

class LogHandler(FileSystemEventHandler):
    def __init__(self, filepath):
        self.filepath = filepath
        self._file = open(filepath, 'r')
        self._file.seek(0, os.SEEK_END)
        self.conn = None
        self.cursor = None
        self.user_key = None
        self._setup_db_and_key()

    def _setup_db_and_key(self):
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("[INFO] DB connection established.")

            user_password = config("USER_PASSWORD", default=None)
            if not user_password:
                raise Exception("USER_PASSWORD env var missing")

            self.cursor.execute("SELECT kdf_salt FROM users LIMIT 1")
            row = self.cursor.fetchone()
            if not row:
                raise Exception("No user salt found")
            
            kdf_salt = row[0]
            self.user_key = derive_aes_key(user_password, kdf_salt)
        except Exception as e:
            print(f"[ERROR] Failed to set up DB/key: {e}")
            self.cleanup()
            exit(1)

    def save_log(self, parsed):
        try:
            ts, host, service, msg = parsed
            state = get_state(msg)
            enc_host = encrypt_data(host, self.user_key)
            enc_service = encrypt_data(service, self.user_key)
            enc_msg = encrypt_data(msg, self.user_key)
            query = (
                f"INSERT INTO {TABLE_NAME} (timestamp, hostname, service, message, state) "
                "VALUES (%s, %s, %s, %s, %s)"
            )
            self.cursor.execute(query, (ts, enc_host, enc_service, enc_msg, state))
            self.conn.commit()
            # Touch the update file
            pathlib.Path(".log_update").touch()
            print(f"[SAVED] {parsed} with state: {state}")
        except Exception as e:
            print(f"[ERROR] Failed to insert log: {parsed} - {e}")

    def process_new_lines(self):
        while True:
            line = self._file.readline()
            if not line:
                break
            parsed = parse_log_line(line)
            if parsed:
                self.save_log(parsed)

    def on_modified(self, event):
        if os.path.abspath(event.src_path) == os.path.abspath(self.filepath):
            self.process_new_lines()

    def cleanup(self):
        try:
            if self._file:
                self._file.close()
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            print("[INFO] Resources cleaned up.")
        except Exception:
            pass

if __name__ == "__main__":
    abs_log_path = os.path.abspath(LOG_FILE)
    handler = LogHandler(abs_log_path)
    observer = Observer()
    observer.schedule(handler, path=os.path.dirname(abs_log_path), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    finally:
        handler.cleanup()
        observer.join()
