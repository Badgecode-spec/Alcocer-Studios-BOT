#!/bin/bash
# Alcocer Studios BOT — Server Setup Script
# Run as root on a fresh Ubuntu/Debian VPS:
#   bash setup.sh
set -e

REPO_URL="https://github.com/Badgecode-spec/Alcocer-Studios-BOT.git"
BRANCH="claude/automated-outreach-bot-WNiCA"
INSTALL_DIR="/opt/alcocer-bot"
SERVICE_NAME="alcocer-bot"

echo ""
echo "========================================"
echo "  Alcocer Studios BOT — Server Setup"
echo "========================================"
echo ""

# --- 1. System dependencies ---
echo "[1/6] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl
echo "      Done."

# --- 2. Clone or update repo ---
echo "[2/6] Cloning repository..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "      Directory exists — pulling latest..."
    git -C "$INSTALL_DIR" fetch origin
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull origin "$BRANCH"
else
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi
echo "      Done."

# --- 3. Python virtual environment ---
echo "[3/6] Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
echo "      Done."

# --- 4. .env file ---
echo "[4/6] Configuring environment..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo ""
    echo "  *** ACTION REQUIRED ***"
    echo "  Fill in your API keys in: $INSTALL_DIR/.env"
    echo ""
    echo "  You can do this now with:"
    echo "    nano $INSTALL_DIR/.env"
    echo ""
    read -p "  Press ENTER when you have saved your .env file..." _
else
    echo "      .env already exists — skipping."
fi

# --- 5. Systemd service ---
echo "[5/6] Installing systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Alcocer Studios Outreach Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
echo "      Done."

# --- 6. Start the service ---
echo "[6/6] Starting the bot..."
systemctl restart "$SERVICE_NAME"
sleep 2

STATUS=$(systemctl is-active "$SERVICE_NAME")
if [ "$STATUS" = "active" ]; then
    echo ""
    echo "========================================"
    echo "  BOT IS RUNNING"
    echo "========================================"
else
    echo ""
    echo "  WARNING: Service may not have started. Check with:"
    echo "    systemctl status $SERVICE_NAME"
fi

echo ""
echo "  Useful commands:"
echo "    View live logs:   journalctl -u $SERVICE_NAME -f"
echo "    Check status:     systemctl status $SERVICE_NAME"
echo "    Restart bot:      systemctl restart $SERVICE_NAME"
echo "    Stop bot:         systemctl stop $SERVICE_NAME"
echo "    Local log file:   tail -f $INSTALL_DIR/bot.log"
echo ""
echo "  To update the bot after code changes:"
echo "    cd $INSTALL_DIR && git pull && systemctl restart $SERVICE_NAME"
echo ""
