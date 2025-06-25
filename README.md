# logcrypt: Secure Log Monitoring & User Management

                           ██▓     ▒█████    ▄████  ▄████▄   ██▀███ ▓██   ██▓ ██▓███  ▄▄▄█████▓
                           ▓██▒    ▒██▒  ██▒ ██▒ ▀█▒▒██▀ ▀█  ▓██ ▒ ██▒▒██  ██▒▓██░  ██▒▓  ██▒ ▓▒
                           ▒██░    ▒██░  ██▒▒██░▄▄▄░▒▓█    ▄ ▓██ ░▄█ ▒ ▒██ ██░▓██░ ██▓▒▒ ▓██░ ▒░
                           ▒██░    ▒██   ██░░▓█  ██▓▒▓▓▄ ▄██▒▒██▀▀█▄   ░ ▐██▓░▒██▄█▓▒ ▒░ ▓██▓ ░ 
                           ░██████▒░ ████▓▒░░▒▓███▀▒▒ ▓███▀ ░░██▓ ▒██▒ ░ ██▒▓░▒██▒ ░  ░  ▒██▒ ░ 
                           ░ ▒░▓  ░░ ▒░▒░▒░  ░▒   ▒ ░ ░▒ ▒  ░░ ▒▓ ░▒▓░  ██▒▒▒ ▒▓▒░ ░  ░  ▒ ░░   
                           ░ ░ ▒  ░  ░ ▒ ▒░   ░   ░   ░  ▒     ░▒ ░ ▒░▓██ ░▒░ ░▒ ░         ░    
                           ░ ░   ░ ░ ░ ▒  ░ ░   ░ ░          ░░   ░ ▒ ▒ ░░  ░░         ░       v1.0.0`
                              ░  ░    ░ ░        ░ ░ ░         ░     ░ ░                       
                                                   ░                 ░ ░                       


**logcrypt** is a secure, terminal-based application for managing users and monitoring system authentication logs. It features encrypted log storage, user authentication, and a modern TUI (Textual User Interface) for log viewing and user management.

---

## Features

- **User Management**: Secure user creation and authentication with password hashing and salted key derivation.
- **Encrypted Log Storage**: All sensitive log data is encrypted using AES before being stored in the database.
- **Live Log Monitoring**: Real-time ingestion of `/var/log/auth.log` with automatic parsing and classification.
- **Modern TUI**: Built with [Textual](https://textual.textualize.io/), providing a responsive and interactive terminal UI for login, user creation, and log viewing.
- **Service Loader**: Smart loader checks and starts required services (MariaDB, rsyslogd, ssh, application) and handles first-run setup.
- **Search & Filter**: Quickly search and filter logs in the viewer.
- **Auto-Login**: Supports auto-login via environment variable for seamless integration with the loader.

---

## Architecture Overview

- **main.py**: Entry point for the TUI, handles loader integration, user authentication, and application state.
- **loader.py**: Checks and starts required services, manages first-run and resume logic, and provides a loader UI.
- **log.py**: Watches `/var/log/auth.log`, parses new entries, encrypts, and stores them in the database.
- **eye_view.py**: TUI log viewer with search/filter, auto-login, and error handling.
- **lib.py**: Shared cryptographic and database utilities.

---

## Database Schema

- **users**: Stores usernames, password hashes, and KDF salts.
- **auth_logs**: Stores encrypted log entries with timestamp, hostname, service, message, and state.

---

## Getting Started

### Prerequisites

- [uv](https://github.com/astral-sh/uv) (latest version)
- MariaDB server

> **Note:** You do **not** need to manually install Python dependencies or manage virtual environments.  
> `uv` will handle all dependency management automatically.

### Setup

1. **Clone the repository**  
   ```sh
   git clone <your-repo-url>
   cd logcrypt/docker
   ```

2. **Configure MariaDB**  
   - Ensure MariaDB is running.
   - Create the `groot` database and user, and grant privileges:
     ```sql
     CREATE DATABASE groot;
     CREATE USER 'groot'@'localhost' IDENTIFIED BY 'groot';
     GRANT ALL PRIVILEGES ON groot.* TO 'groot'@'localhost';
     FLUSH PRIVILEGES;
     ```
   - Create the required tables:
     ```sql
     USE groot;
     CREATE TABLE users (
         id INT AUTO_INCREMENT PRIMARY KEY,
         username VARCHAR(255) UNIQUE NOT NULL,
         password_hash VARCHAR(255) NOT NULL,
         kdf_salt BLOB NOT NULL
     );
     CREATE TABLE auth_logs (
         id INT AUTO_INCREMENT PRIMARY KEY,
         timestamp DATETIME NOT NULL,
         hostname TEXT NOT NULL,
         service TEXT NOT NULL,
         message TEXT NOT NULL,
         state VARCHAR(32) NOT NULL
     );
     ```

3. **Run the Application**  
   ```sh
   uv run main.py
   ```
   - On first run, you'll be prompted to create the initial user.
   - The loader will check/start required services and launch the TUI.

---

## Usage

- **Login**: Enter your username and password to access the log viewer.
- **Log Viewer**: View, search, and filter recent authentication logs.
- **Continue/Restart Dialog**: If the application is already running, choose to continue (view logs) or restart the service.

---

## Security

- Passwords are hashed with SHA-256.
- Per-user AES keys are derived using PBKDF2 with a unique salt.
- All log data is encrypted before storage.
- Environment variables are used for sensitive runtime secrets and cleared after use.

---

## Code Structure

```
logcrypt/
├── main.py         # TUI entry point and app logic
├── loader.py       # Service loader and setup
├── log.py          # Log ingestion and encryption
├── eye_view.py     # Log viewer TUI
├── lib.py          # Crypto and DB utilities
├── style.tcss      # Textual CSS for UI styling
├── pyproject.toml  # package manager for uv
```

---

## Troubleshooting

- **Database Connection Errors**: Ensure MariaDB is running and credentials match those in `lib.py`.
- **Permission Issues**: The app may require elevated permissions to read `/var/log/auth.log`.
- **Service Startup**: The loader will attempt to start required services; check logs for errors if startup fails.

---

## License

This project is for educational and demonstration purposes.  
For production use, review and enhance security, error handling, and configuration management.

---

## Credits

- Built with [Textual](https://github.com/Textualize/textual)
- Uses [PyCryptodome](https://www.pycryptodome.org/) for cryptography
- Uses [Watchdog](https://github.com/gorakhargosh/watchdog) for log file monitoring

---

**Contributions and feedback are welcome!**  
Please open issues or submit pull requests for improvements, bug fixes, or new features.