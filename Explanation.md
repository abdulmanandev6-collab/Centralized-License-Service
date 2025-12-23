# Centralized License Service - Explanation

## Problem and Requirements

group.one manages multiple WordPress brands and needs a centralized license service to track licenses across all brands. The service must provision licenses, support multiple products per key, keep brands isolated, allow activation/validation, handle seat management, and support lifecycle operations (suspend, resume, cancel, renew).

## Architecture and Design

**Tech Stack:** Django REST Framework with PostgreSQL. Handles multi-tenancy well and provides good structure.

**Data Model:** Brand → Product → License → Activation
- Brand: Isolated tenants with API keys
- Product: Belongs to a brand
- LicenseKey: Customer-facing key that unlocks multiple licenses
- License: Product license with status, expiration, seat limits
- Activation: Tracks where license is used (site URL, machine ID)

Multi-tenancy uses shared database with app-level isolation. Queries scoped by brand, except US6 which allows cross-brand email queries for support.

**API Design:**
- **Brand API** (`/api/brand/`): Uses `X-API-Key` header. Handles provisioning, lifecycle, cross-brand queries. For brand systems only.
- **Product API** (`/api/product/`): Uses `X-License-Key` header. Handles activation, status checks, seat deactivation. For end-user products.

**Database:** PostgreSQL with UUIDs, indexes on frequent queries, unique constraints. `unique_together` on Activation prevents duplicate active activations.

**Observability:** Logging for key operations, health check endpoint, custom exception handler.

## Trade-offs and Decisions

**Shared Database:** App-level isolation is simpler to operate and enables cross-brand queries. Can move to separate DBs later if needed.

**API Keys vs OAuth:** Simple API keys work well for server-to-server. Can upgrade to OAuth later.

**Seat Management:** Fully implemented as it's core functionality.

**License Key Format:** Human-readable format (e.g., "GHX6-889J-WUIE-02R2") for better UX than UUIDs.

**Scaling:** Supports horizontal scaling. Would add Redis caching and rate limiting at scale. Read replicas possible for status checks.

## How Solution Satisfies Each User Story

**US1: Brand can provision a license** `POST /api/brand/licenses/`
Creates license keys and licenses for customer email. Supports: new purchase → new key, addon → adds to existing key, different brand → new key. Uses `get_or_create` to prevent duplicates.

**US2: Brand can change license lifecycle** `PATCH /api/brand/licenses/{license_id}/lifecycle/`
Supports renew (extend expiration), suspend, resume, cancel. Validates brand ownership and license state.

**US3: End-user product can activate a license** `POST /api/product/activate/`
Activates for specific instance (site URL, machine ID). Enforces seat limits, prevents duplicate activations.

**US4: User can check license status** `GET /api/product/check/`
Returns license key info, all associated licenses, status, expiration, seat usage.

**US5: End-user product can deactivate a seat** `POST /api/product/deactivate/`
Deactivates specific activation to free up a seat.

**US6: Brands can list licenses by email across all brands** `GET /api/brand/licenses/by-email/?email=...`
Cross-brand query. Brand-only access. Returns all licenses for email across all brands.

## How to Run Locally

### Docker (Recommended)
```bash
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py setup_test_data
```
Access: API http://localhost:8000, Swagger http://localhost:8000/docs/, Admin http://localhost:8000/admin/

### Local Development
1. Install PostgreSQL 15+, create database `license_service`
2. `python -m venv venv && source venv/bin/activate`
3. `pip install -r requirements.txt`
4. Set env vars (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, etc.)
5. `python manage.py migrate && python manage.py setup_test_data && python manage.py runserver`

### Test Credentials
After `setup_test_data`, API keys printed: RankMath `rankmath-api-key-sgxOdIvSv-_BBnTBfRQc3w`, WP Rocket `wprocket-api-key-T3nmHuBuh30dT5zP872JWw`. Use in `X-API-Key` header for brand endpoints. Use `license_key` from provision response in `X-License-Key` header for product endpoints.

### Sample Requests
**Provision:** `curl -X POST http://localhost:8000/api/brand/licenses/ -H "Content-Type: application/json" -H "X-API-Key: rankmath-api-key-sgxOdIvSv-_BBnTBfRQc3w" -d '{"customer_email": "john@example.com", "products": [{"slug": "rankmath", "expiration_date": "2025-12-31T23:59:59", "max_seats": 5}]}'`

**Activate:** `curl -X POST http://localhost:8000/api/product/activate/ -H "Content-Type: application/json" -H "X-License-Key: {license_key}" -d '{"instance_id": "https://example.com", "product_slug": "rankmath"}'`

**Check:** `curl -X GET http://localhost:8000/api/product/check/ -H "X-License-Key: {license_key}"`

See Swagger docs at http://localhost:8000/docs/ for all endpoints.

## Known Limitations and Next Steps

**Limitations:** No rate limiting, caching, webhooks, audit trail, bulk operations, API key rotation, or license key versioning. All operations synchronous.

**Next Steps:** Short-term: test suite, CI/CD, rate limiting, Redis caching, monitoring. Medium-term: webhooks, audit logging, bulk operations, admin dashboard. Long-term: read replicas, event-driven architecture, multi-region support.

Current architecture is flexible and can evolve without major rewrites.
