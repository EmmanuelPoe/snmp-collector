.PHONY: loadtest backup restore help setup ensure-env ensure-dirs build up down logs logs-backend logs-frontend logs-manager clean reset migrate shell-backend shell-db test simulation clean-simulation status restart-backend restart-frontend restart-exporter dev-frontend dev-backend

# Create .env from the example on first run, generating strong random secrets so
# the stack starts securely out of the box (the services refuse to start with the
# placeholder secrets shipped in .env.example). ENCRYPTION_KEY is left empty and
# derived from JWT_SECRET; set a dedicated one for production.
ensure-env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		python3 -c "import secrets, re, pathlib; p = pathlib.Path('.env'); t = p.read_text(); sub = lambda t, k: re.sub(r'(?m)^' + k + r'=.*', k + '=' + secrets.token_urlsafe(32), t); t = sub(t, 'JWT_SECRET'); t = sub(t, 'MANAGER_API_KEY'); p.write_text(t)" \
			&& echo "Created .env with generated JWT_SECRET and MANAGER_API_KEY" \
			|| echo "Created .env — set JWT_SECRET and MANAGER_API_KEY to strong random values before starting"; \
	fi

# Pre-create bind-mounted data dirs. Without this, Docker creates them root-owned
# on a fresh Linux checkout and the manager (non-root uid 100) cannot open DuckDB
# ("Permission denied"). Only newly created dirs are chmod'd; existing ones are
# left untouched. Revisit with named volumes in the production overlay (Step 4.3).
ensure-dirs:
	@for d in data/db data/dead-letter data/registry data/agent-queue data/agent-id; do \
		if [ ! -d $$d ]; then \
			mkdir -p $$d && chmod 777 $$d; \
		fi; \
	done

# Default target
help:
	@echo "SNMP Metrics Collector - Makefile Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo "  setup          - First-time setup: build + start + migrate (one command)"
	@echo "  build          - Build all Docker containers"
	@echo "  up             - Start the application"
	@echo "  down           - Stop the application"
	@echo "  logs           - View logs from all containers"
	@echo "  logs-backend   - View backend logs"
	@echo "  logs-frontend  - View frontend logs"
	@echo "  logs-manager   - View manager logs"
	@echo "  clean          - Remove containers and volumes"
	@echo "  reset          - Full reset (clean + rebuild + start)"
	@echo "  migrate        - Run database migrations"
	@echo "  shell-backend  - Open shell in backend container"
	@echo "  shell-db       - Open PostgreSQL shell"
	@echo "  test           - Run manager tests"
	@echo "  simulation     - Run end-to-end simulation test with SNMP simulator"
	@echo "  clean-simulation - Remove test data from simulation"
	@echo ""

# First-time setup: build, start, and migrate in one command
setup: ensure-env ensure-dirs
	docker-compose build
	docker-compose up -d
	@echo "Waiting for backend to be ready..."
	@until docker-compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1; do sleep 2; done
	docker-compose exec -T backend alembic upgrade head
	@echo ""
	@echo "Ready at http://localhost  (login as admin@localhost — the one-time password is printed in 'make logs-backend')"

# Build all containers
build:
	@echo "Building Docker containers..."
	docker-compose build

# Start the application
up: ensure-env ensure-dirs
	@echo "Starting SNMP Collector application..."
	docker-compose up -d
	@echo ""
	@echo "✅ Application started successfully!"
	@echo ""
	@echo "Access the application:"
	@echo "  App:         http://localhost"
	@echo "  Manager API: http://localhost:8001"
	@echo ""
	@echo "First login (admin@localhost):"
	@echo "  The one-time password is printed once in the backend log — run 'make logs-backend'"
	@echo "  You will be prompted to change it on first login"
	@echo ""
	@echo "View logs: make logs"
	@echo "Stop application: make down"

# Stop the application
down:
	@echo "Stopping SNMP Collector application..."
	docker-compose down

# View logs
logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

logs-manager:
	docker-compose logs -f manager

# Clean up containers and volumes
clean:
	@echo "Cleaning up containers and volumes..."
	docker-compose down -v
	@echo "✅ Cleanup complete"

# Full reset
reset: clean build up
	@echo "✅ Full reset complete"

# Run database migrations
migrate:
	@echo "Running database migrations..."
	docker-compose exec backend alembic upgrade head
	@echo "✅ Migrations complete"

# Open shell in backend container
shell-backend:
	docker-compose exec backend /bin/sh

# Open PostgreSQL shell
shell-db:
	docker-compose exec postgres psql -U snmpuser -d snmp_metrics

# Run tests
test:
	@echo "Running manager tests..."
	docker-compose exec manager pytest tests/ -v

# Development helpers
dev-frontend:
	cd frontend && npm start

dev-backend:
	cd backend && uvicorn main:app --reload

# Check status
status:
	docker-compose ps

# Restart specific service
restart-backend:
	docker-compose restart backend

restart-frontend:
	docker-compose restart frontend

restart-exporter:
	docker-compose restart snmp-exporter

# Run simulation test
simulation:
	@echo "🧪 Running SNMP simulation test..."
	@echo "This will:"
	@echo "  1. Start all containers (including SNMP simulator)"
	@echo "  2. Authenticate and add a test device via API"
	@echo "  3. Wait 90s for the agent to complete its first poll cycle"
	@echo "  4. Verify metrics are stored in DuckDB and readable via the API"
	@echo ""
	@docker-compose up -d
	@echo "Waiting for services to start..."
	@sleep 10
	@echo "Running database migrations..."
	@docker-compose exec -T backend alembic upgrade head
	@bash scripts/run_simulation.sh

# Clean simulation data
clean-simulation:
	@echo "Cleaning simulation test data..."
	docker-compose exec -T postgres psql -U snmpuser -d snmp_metrics -c \
		"DELETE FROM snmp_metrics WHERE device_id IN (SELECT id FROM devices WHERE name = 'Test-Simulator');" || true
	docker-compose exec -T postgres psql -U snmpuser -d snmp_metrics -c \
		"DELETE FROM collection_schedules WHERE device_id IN (SELECT id FROM devices WHERE name = 'Test-Simulator');" || true
	docker-compose exec -T postgres psql -U snmpuser -d snmp_metrics -c \
		"DELETE FROM devices WHERE name = 'Test-Simulator';" || true
	@echo "✓ Simulation data cleaned"

# Backup + restore (Step 2.4) — artifacts in ./backups; see docs/runbooks/restore.md
backup:
	@./scripts/backup.sh

restore:
	@test -n "$(BACKUP)" || (echo "usage: make restore BACKUP=<timestamp>  (see ls backups/)" && exit 1)
	@./scripts/restore.sh $(BACKUP)

# Load test at the 1000-device target (Step 2.5) — see docs/scale-benchmark.md
loadtest:
	@echo "🏋️  Load test: synthetic ingest (120s) + query fleet (60s)"
	@set -a && . ./.env && set +a && \
	python3 scripts/loadtest/ingest_load.py --devices 1000 --duration 120 --concurrency 4 --api-key "$$MANAGER_API_KEY" && \
	echo "" && \
	python3 scripts/loadtest/query_load.py --password "$${SIM_ADMIN_PASSWORD:?set SIM_ADMIN_PASSWORD to the admin password}" --duration 60
	@echo ""
	@echo "Container resource snapshot (feeds Step 4.2 limits):"
	@docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' || true
