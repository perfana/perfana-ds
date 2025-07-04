# Perfana Data-Science FastAPI Service

A FastAPI-based data science service for Perfana performance analytics platform, providing data pipelines, metrics collection, and performance analysis capabilities.

## Table of Contents

- [Project Organization](#project-organization)
- [Setup](#setup)
- [Running the Application](#running-the-application)
- [Development](#development)
- [Testing](#testing)
- [API Documentation](#api-documentation)
- [Contributing](#contributing)

## Project Organization

```
├── src/
│   ├── perfana_ds/             <- Core data pipelines package, built using MongoDB aggregations
│   │   ├── catalog/            <- Data catalog and dataset management
│   │   ├── common/             <- Common utilities and helpers
│   │   ├── datasets/           <- Dataset abstractions and MongoDB interfaces
│   │   ├── pipelines/          <- Data processing pipelines
│   │   └── schemas/            <- Pydantic schemas and data models
│   └── perfana_ds_api/         <- FastAPI service and Celery tasks
│       ├── routes/             <- API route definitions
│       ├── app.py              <- FastAPI application setup
│       └── worker.py           <- Celery worker configuration
├── tests/                      <- Unit and integration tests
├── documentation/              <- Project documentation
├── notebooks/                  <- Jupyter notebooks for analysis
├── environment.yml             <- Conda environment definition
├── pyproject.toml              <- Python project configuration
├── Dockerfile                  <- Docker image definition
├── VERSION                     <- Version file
└── README.md                   <- This file
```

## Setup

### Prerequisites

- Python 3.10 or higher
- MongoDB (for data storage)
- Grafana (for metrics collection)

### Environment Setup

#### Option 1: Using Conda (Recommended)

```bash
# Create and activate conda environment
conda env create -f environment.yml
conda activate perfana-ds
```

#### Option 2: Using pip

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev,test]"
```

### Environment Variables

Create a `.env` file in the root directory:

```env
PROJECT_NAME="Perfana Datascience"
MONGO_URL="mongodb://root:password@localhost:27018/?directConnection=true"
MONGO_DB="perfana"

GRAFANA_URL="http://localhost:3000"
GRAFANA_CONCURRENCY=30
GRAFANA_BATCH_SIZE=20
```

### Pre-commit Setup

Install pre-commit hooks to ensure code quality:

```bash
pre-commit install
```

This will automatically run:
- `black` for code formatting
- `ruff` for linting
- `mypy` for type checking

## Running the Application

The application consists of a FastAPI service and two Celery workers.

### FastAPI Service

```bash
uvicorn perfana_ds_api.app:app --port 8080
```

### Celery Workers

#### Default Worker
Handles most background tasks:

```bash
# Development (Windows)
celery -A perfana_ds_api.worker worker --pool=solo --loglevel=info -Q celery

# Production
celery -A perfana_ds_api.worker worker -c 5 --loglevel=info -Q celery
```

#### Metrics Worker
Specialized for Grafana metrics collection:

```bash
# Development (Windows)
celery -A perfana_ds_api.worker worker --pool=solo --loglevel=info -Q metrics

# Production
celery -A perfana_ds_api.worker worker -c 5 --loglevel=info -Q metrics
```

Tune concurrency to avoid overloading the Grafana server with HTTP requests.


## Development

### Code Quality Tools

```bash
# Format code
black src/

# Lint code
ruff check src/

# Type checking
mypy src/

# Run all checks
pre-commit run --all-files
```

### Development Dependencies

Install additional development tools:

```bash
# Using conda
conda env update -f environment.yml

# Using pip
pip install -e ".[dev]"
```

This includes:
- `plotly` and `matplotlib` for visualizations
- `pre-commit` for code quality hooks

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=perfana_ds --cov-report=html

# Run specific test file
pytest tests/test_check_pipeline_integration.py

# Run with verbose output
pytest -v
```

### Test Configuration

Tests are configured in `pyproject.toml` with:
- Coverage reporting
- Test discovery in `src/tests/`
- Environment loading from `tests/test.env`

### Test Structure

- `tests/routes/` - API endpoint tests
- `tests/schemas/` - Schema validation tests
- `tests/fixture/` - Test data fixtures
- `tests/test_*.py` - Integration tests

## API Documentation

### Interactive Documentation

Once the FastAPI service is running, access interactive API documentation at:

- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`

### API Endpoints

- `/health` - Health check endpoint
- `/data/*` - Data retrieval and processing endpoints
- `/manage/*` - Management and administrative endpoints

## Contributing

### Development Workflow

1. **Fork and clone** the repository
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Install dependencies**: `conda env create -f environment.yml`
4. **Install pre-commit hooks**: `pre-commit install`
5. **Make your changes** following the coding standards
6. **Run tests**: `pytest`
7. **Commit changes**: `git commit -m "Add your feature"`
8. **Push to branch**: `git push origin feature/your-feature`
9. **Create Pull Request**

### Code Standards

- Follow PEP 8 style guidelines
- Use type hints for all functions
- Write docstrings for public APIs
- Use meaningful variable and function names

### Commit Messages

Use conventional commit format:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `refactor:` for code refactoring
- `test:` for adding tests

---

**Version**: 1.0.0  
**Maintainer**: Lodewic van Twillert (lodewic@perfana.io)  / Daniel Moll (daniel@perfana.io)
**Homepage**: https://github.com/perfana