USER=adrian
HOST=nas
TARGET_DIR=/volume3/docker/flathunters

DOCKER=/usr/local/bin/docker
DOCKER_COMPOSE=/usr/local/bin/docker-compose

EXCLUDES=--exclude '.git' --exclude '__pycache__' --exclude '.venv' --exclude '.idea' --exclude 'processed_ids.db'

.PHONY: push build run deploy logs stop

# The "Do Everything" command
deploy: push build run

push:
	@echo "🚀 Syncing code to NAS..."
	rsync -avz $(EXCLUDES) ./ $(USER)@$(HOST):$(TARGET_DIR)

build:
	@echo "🚀 Building docker image on NAS..."
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && $(DOCKER) build . -t flathunters-app"

run:
	@echo "🏗️  Starting container on NAS..."
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && $(DOCKER) compose up -d"

logs:
	@echo "📋 Showing logs on NAS..."
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && $(DOCKER) compose logs -f"

stop:
	@echo "🛑 Stopping service on NAS..."
	ssh $(USER)@$(HOST) "cd $(TARGET_DIR) && $(DOCKER) compose down"
