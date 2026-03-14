# --- Configuration ---
USER=adrian
HOST=server
TARGET_DIR=/home/adrian/flathunters
# Add any files/folders you DON'T want on the server
EXCLUDES=--exclude '.git' --exclude '__pycache__' --exclude 'node_modules' --exclude '.env'

.PHONY: deploy push build run stop

# The "Do Everything" command
deploy: push run

# Syncs local code to the server
push:
	@echo "🚀 Syncing code to $(HOST)..."
	rsync -avz $(EXCLUDES) ./ $(USER)@$(HOST):$(TARGET_DIR)

# Builds and starts the container on the remote server
run:
	@echo "🏗️  Building and starting containers on $(HOST)..."
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && sudo docker compose up -d --build"

# View logs on the server
logs:
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && sudo docker compose logs -f"

# Stop the service on the server
stop:
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && sudo docker compose down"
