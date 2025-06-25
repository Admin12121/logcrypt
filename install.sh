#!/bin/bash
set -euo pipefail

print_banner() {
cat <<'EOF'
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
                                                                                                        
                                Made by Vicky Tajpuriya aka admin12121                                                                                                        
EOF
}

detect_env() {
    if [ -f /.dockerenv ] || grep -qE '/docker|/lxc' /proc/1/cgroup; then
        echo "Running inside a Docker container."
        SUDO=""
    else
        echo "Running on a real (non-Docker) system."
        SUDO="sudo"
        $SUDO -v
    fi
}

install_dependencies() {
    $SUDO apt update
    $SUDO apt install -y python3 openssh-server mariadb-server rsyslog curl
}

install_uv() {
    if ! command -v uv &>/dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi
    [ -f "$HOME/.local/bin/env" ] && source "$HOME/.local/bin/env"
}

configure_services() {
    [ -f /etc/rsyslog.conf ] && $SUDO sed -i 's/^\s*module(load="imklog")/# &/' /etc/rsyslog.conf || true
    [ -f /etc/rsyslog.conf ] && $SUDO sed -i 's/^#\?\s*SyslogFacility.*/SyslogFacility AUTH/' /etc/rsyslog.conf || true
    [ -f /etc/rsyslog.conf ] && $SUDO sed -i 's/^#\?\s*LogLevel.*/LogLevel VERBOSE/' /etc/rsyslog.conf || true
    [ -f /etc/ssh/sshd_config ] && $SUDO sed -i 's/^#\?\s*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config || true
}

start_service() {
    $SUDO $service
    echo "$service is already running."

}


setup_database() {
    read -p "Enter database name (default: grooot): " dbname
    dbname=${dbname:-grooot}
    read -p "Enter table name (default: auth_log): " tablename
    tablename=${tablename:-auth_log}
    read -p "Enter username for database (default: grooot): " dbuser
    dbuser=${dbuser:-grooot}
    read -s -p "Enter password for user $dbuser (default: grooot): " dbpass
    echo
    dbpass=${dbpass:-grooot}

    sql="
    CREATE DATABASE IF NOT EXISTS \`${dbname}\`;
    USE \`${dbname}\`;

    CREATE TABLE IF NOT EXISTS \`${tablename}\` (
        id INT(11) NOT NULL AUTO_INCREMENT,
        timestamp DATETIME DEFAULT NULL,
        hostname VARCHAR(255) DEFAULT NULL,
        service VARCHAR(255) DEFAULT NULL,
        message TEXT DEFAULT NULL,
        state VARCHAR(255) DEFAULT NULL,
        PRIMARY KEY (id)
    );

    CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(255) NOT NULL,
        password_hash TEXT NOT NULL,
        kdf_salt VARBINARY(16) NOT NULL
    );

    CREATE USER IF NOT EXISTS '${dbuser}'@'localhost' IDENTIFIED BY '${dbpass}';
    GRANT ALL PRIVILEGES ON \`${dbname}\`.* TO '${dbuser}'@'localhost';
    FLUSH PRIVILEGES;
    "

    echo "$sql" | mysql -u root

    cat > .env <<EOF
DB_NAME=${dbname}
DB_USER=${dbuser}
DB_PASS=${dbpass}
TABLE_NAME=${tablename}
EOF
}

create_logcrypt_launcher() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cat <<EOF | $SUDO tee /usr/sbin/logcrypt > /dev/null
#!/bin/bash
uv run "$SCRIPT_DIR/main.py"
EOF
    $SUDO chmod +x /usr/sbin/logcrypt
}

main() {
    print_banner
    detect_env
    install_dependencies
    install_uv
    configure_services
    start_service rsyslogd
    start_service sshd
    start_service mariadb
    setup_database
    create_logcrypt_launcher
    echo "LogCrypt installation complete."
    echo "Enter 'logcrypt' to start the application."
}

main "$@"