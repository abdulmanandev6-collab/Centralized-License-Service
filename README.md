# Centralized License Service

A multi-tenant license management service for group.one brands.

## Quick Start

### Using Docker (Recommended)

```bash
# Start services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser (optional)
docker-compose exec web python manage.py createsuperuser
```

### Local Development

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. Set up database:
```bash
# Make sure PostgreSQL is running
python manage.py migrate
```

5. Run server:
```bash
python manage.py runserver
```

## API Endpoints

### Brand API (requires X-API-Key header)
- `POST /api/brand/licenses/` - Provision a license
- `POST /api/brand/licenses/{license_key}/add-product/` - Add product to license key
- `GET /api/brand/licenses/by-email/?email=...` - List licenses by email

### Product API (requires X-License-Key header)
- `POST /api/product/activate/` - Activate a license
- `GET /api/product/check/` - Check license status

### Health Check
- `GET /api/health/` - Service health check

## Project Structure

```
license_service/
├── license_service/          # Django project settings
├── licenses/                 # Main application
│   ├── models.py            # Data models
│   ├── views/               # API views
│   ├── urls/                # URL routing
│   ├── authentication.py    # Auth classes
│   └── exceptions.py        # Error handling
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker configuration
└── docker-compose.yml      # Docker Compose setup
```
