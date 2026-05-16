# ============================================
# AI OS - Build Automation Makefile
# ============================================

.PHONY: install run docker-up docker-down docker-logs migrate test format

# Install all dependencies (production + development)
install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	@echo "✅ Installation complete!"

# Run FastAPI application with hot reload
run:
	@echo "🚀 Starting AI OS..."
	uvicorn app.main:app --reload --host 0.0.0.0 --port $${PORT:-8000}

# Start Docker services in detached mode
docker-up:
	@echo "🐳 Starting Docker services..."
	docker compose up -d
	@echo "✅ Docker services started!"

# Stop Docker services
docker-down:
	@echo "🛑 Stopping Docker services..."
	docker compose down
	@echo "✅ Docker services stopped!"

# View Docker service logs (follow mode)
docker-logs:
	@echo "📋 Viewing Docker logs..."
	docker compose logs -f

# Run database migrations
migrate:
	@echo "🔄 Running database migrations..."
	alembic upgrade head
	@echo "✅ Migrations complete!"

# Run test suite with verbose output
test:
	@echo "🧪 Running tests..."
	pytest tests/ -v
	@echo "✅ Tests complete!"

# Format code with black and isort
format:
	@echo "🎨 Formatting code..."
	black app/ tests/
	isort app/ tests/
	@echo "✅ Code formatting complete!"
