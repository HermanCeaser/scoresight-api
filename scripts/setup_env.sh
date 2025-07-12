#!/usr/bin/env bash
set -e

# Virtual Environment Setup Script for ScoreSight
# Usage: ./scripts/setup_env.sh [dev|prod]

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the project directory
PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)
VENV_DIR="${PROJECT_DIR}/venv"

# Default environment
ENVIRONMENT=${1:-dev}

echo -e "${BLUE}🔧 ScoreSight Environment Setup${NC}"
echo -e "${BLUE}================================${NC}"
echo -e "Project directory: ${PROJECT_DIR}"
echo -e "Environment: ${ENVIRONMENT}"
echo ""

# Function to create virtual environment
create_venv() {
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        echo -e "${GREEN}✅ Virtual environment created at ${VENV_DIR}${NC}"
    else
        echo -e "${GREEN}✅ Virtual environment already exists${NC}"
    fi
}

# Function to activate virtual environment
activate_venv() {
    echo -e "${YELLOW}🔌 Activating virtual environment...${NC}"
    source "${VENV_DIR}/bin/activate"
    echo -e "${GREEN}✅ Virtual environment activated${NC}"
}

# Function to upgrade pip
upgrade_pip() {
    echo -e "${YELLOW}⬆️  Upgrading pip...${NC}"
    pip install --upgrade pip
    echo -e "${GREEN}✅ Pip upgraded${NC}"
}

# Function to install requirements
install_requirements() {
    echo -e "${YELLOW}📚 Installing requirements for ${ENVIRONMENT} environment...${NC}"
    
    case $ENVIRONMENT in
        "dev"|"development")
            if [ -f "${PROJECT_DIR}/dev-requirements.txt" ]; then
                pip install -r "${PROJECT_DIR}/dev-requirements.txt"
                echo -e "${GREEN}✅ Development requirements installed${NC}"
            else
                echo -e "${RED}❌ dev-requirements.txt not found${NC}"
                exit 1
            fi
            ;;
        "prod"|"production")
            if [ -f "${PROJECT_DIR}/requirements.txt" ]; then
                pip install -r "${PROJECT_DIR}/requirements.txt"
                echo -e "${GREEN}✅ Production requirements installed${NC}"
            else
                echo -e "${RED}❌ requirements.txt not found${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "${RED}❌ Invalid environment: ${ENVIRONMENT}${NC}"
            echo -e "Usage: $0 [dev|prod]"
            exit 1
            ;;
    esac
}

# Function to create .env file if it doesn't exist
create_env_file() {
    ENV_FILE="${PROJECT_DIR}/.env"
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}📝 Creating .env file...${NC}"
        cat > "$ENV_FILE" << 'EOF'
# ScoreSight Environment Variables

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Database Configuration
# For development (SQLite)
DATABASE_URL=sqlite:///./database/scoresight.db
# For production (MySQL RDS)
# DATABASE_URL=mysql+pymysql://username:password@rds-endpoint:3306/scoresight

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Application Configuration
ENVIRONMENT=development
DEBUG=true
EOF
        echo -e "${GREEN}✅ .env file created. Please update with your actual values.${NC}"
    else
        echo -e "${GREEN}✅ .env file already exists${NC}"
    fi
}

# Function to show activation instructions
show_activation_info() {
    echo ""
    echo -e "${BLUE}🎉 Setup Complete!${NC}"
    echo -e "${BLUE}=================${NC}"
    echo ""
    echo -e "${YELLOW}To activate the virtual environment manually:${NC}"
    echo -e "  source venv/bin/activate"
    echo ""
    echo -e "${YELLOW}To deactivate:${NC}"
    echo -e "  deactivate"
    echo ""
    echo -e "${YELLOW}To run the application:${NC}"
    case $ENVIRONMENT in
        "dev"|"development")
            echo -e "  make dev-full    # Start everything (Redis + Celery + FastAPI)"
            echo -e "  make run         # Start just FastAPI"
            echo -e "  make celery      # Start just Celery worker"
            ;;
        "prod"|"production")
            echo -e "  docker compose up -d    # Start with Docker"
            echo -e "  python app.py           # Start FastAPI directly"
            ;;
    esac
    echo ""
}

# Main execution
main() {
    cd "$PROJECT_DIR"
    
    # Check if Python 3 is available
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is required but not installed${NC}"
        exit 1
    fi
    
    create_venv
    activate_venv
    upgrade_pip
    install_requirements
    create_env_file
    show_activation_info
}

# Run main function
main
