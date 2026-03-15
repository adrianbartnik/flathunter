USER=adrian

# Variables for the Server
HOST_SERVER=server
TARGET_DIR_SERVER=/home/adrian/flathunters

# Variables for the NAS
HOST_NAS=nas
TARGET_DIR_NAS=/var/services/homes/adrian/flathunters

# Logic to switch target based on 'to' variable
# Usage: make deploy (defaults to server)
# Usage: make deploy to=nas
ifeq ($(to),nas)
    HOST := $(HOST_NAS)
    TARGET_DIR := $(TARGET_DIR_NAS)
    LOCATION_NAME := 🏠 NAS
else
    HOST := $(HOST_SERVER)
    TARGET_DIR := $(TARGET_DIR_SERVER)
    LOCATION_NAME := ☁️  SERVER
endif

EXCLUDES=--exclude '.git' --exclude '__pycache__' --exclude '.venv' --exclude '.idea'

.PHONY: deploy push run logs stop

# The "Do Everything" command
deploy: push run

# Syncs local code to the target
push:
	@echo "🚀 Syncing code to $(LOCATION_NAME) ($(HOST))..."
	rsync -avz $(EXCLUDES) ./ $(USER)@$(HOST):$(TARGET_DIR)

# Builds and starts the container on the target
run:
	@echo "🏗️  Building and starting containers on $(LOCATION_NAME)..."
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && docker compose up -d --build"

# View logs on the target
logs:
	@echo "📋 Showing logs for $(LOCATION_NAME)..."
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && docker compose logs -f"

# Stop the service on the target
stop:
	@echo "🛑 Stopping service on $(LOCATION_NAME)..."
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && docker compose down"
