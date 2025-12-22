# Centralized License Service - Explanation

## Problem and Requirements

group.one is bringing together multiple WordPress-focused brands (WP Rocket, Imagify, RankMath, etc.) into a unified ecosystem. The challenge we're solving is that each brand currently manages licenses independently, which creates fragmentation. When a customer buys products from different brands, there's no single place to see what they have access to.

The goal is to build a centralized license service that acts as the single source of truth for all licenses across all brands. This service needs to:

- Handle license provisioning when customers make purchases
- Support multiple products under a single license key (like RankMath + Content AI addon)
- Keep brands isolated (RankMath licenses separate from WP Rocket licenses)
- Allow end-user products to activate and validate licenses
- Support seat management for products that limit activations
- Enable brands to manage license lifecycles (suspend, resume, cancel, renew)
- Provide observability for operations teams

The tricky part is balancing brand isolation with the need for cross-brand queries when needed (like customer support looking up all licenses for an email).

## Architecture and Design

### High-Level Architecture

I went with a Django REST Framework approach because it gives us solid structure out of the box while still being flexible enough to handle our multi-tenant requirements. The service is designed as a stateless API that can scale horizontally.

The architecture follows a clean separation:
- **Models layer**: Core data models with clear relationships
- **Authentication layer**: Two separate auth mechanisms for brands vs end-users
- **Views layer**: Business logic organized by domain (brand operations vs product operations)
- **Serializers**: Request/response validation and transformation

### Data Model

The heart of the system is the relationship between Brands, Products, LicenseKeys, Licenses, and Activations:

```
Brand (RankMath, WP Rocket, etc.)
  └── Product (rankmath, content-ai, wp-rocket)
        └── License (specific product license)
              └── Activation (instance activation)
```

**Brand**: Each brand is a tenant with its own API key. Brands are isolated - RankMath can't see WP Rocket's licenses unless explicitly querying by email (US6).

**Product**: Products belong to a brand. The slug is unique per brand (so RankMath can have "rankmath" and WP Rocket can't, but that's fine since they're different brands).

**LicenseKey**: This is the customer-facing key. One key can unlock multiple licenses (like RankMath + Content AI). Keys are brand-specific - same email, different brand = different key.

**License**: The actual product license with status, expiration, and seat limits. Multiple licenses can share a license key.

**Activation**: Tracks where a license is being used (site URL, machine ID, etc.). Handles seat management.

### Multi-Tenancy Approach

I chose a shared database with brand-based row-level isolation. Each license key is tied to a brand, and all queries are scoped by brand. This keeps things simple while still providing isolation.

For cross-brand queries (US6), I made an exception - brands can query by email across all brands, but only for that specific use case. This is useful for customer support scenarios.

### API Design

The API is split into two main areas:

**Brand API** (`/api/brand/`):
- Uses `X-API-Key` header authentication
- Handles provisioning, lifecycle management, and cross-brand queries
- Only accessible to brand systems

**Product API** (`/api/product/`):
- Uses `X-License-Key` header authentication  
- Handles activation, status checks, and seat deactivation
- Accessible to end-user products

This separation makes it clear who can do what. Brand systems manage licenses, end-user products consume them.

### Integration Points

**For Brand Systems**:
1. When a customer purchases: `POST /api/brand/licenses/` with customer email and products
2. When adding a product to existing key: `POST /api/brand/licenses/{key}/add-product/`
3. When managing lifecycle: `PATCH /api/brand/licenses/{id}/lifecycle/`
4. For customer support: `GET /api/brand/licenses/by-email/?email=...`

**For End-User Products**:
1. On plugin/app startup: `GET /api/product/check/` to validate license
2. When activating: `POST /api/product/activate/` with instance ID
3. When deactivating: `POST /api/product/deactivate/` to free a seat

### Observability

I've added:
- Structured logging with different levels (INFO for operations, DEBUG for troubleshooting)
- Custom exception handler that logs errors with context
- Health check endpoint (`/api/health/`) for monitoring
- Database connection checks in health endpoint

The logging captures key operations like license provisioning, activations, and errors. This helps with debugging and understanding system behavior.

### Database Design

I used PostgreSQL for reliability and to handle the relationships properly. Key design decisions:
- UUIDs for all primary keys (better for distributed systems, no sequential IDs)
- Indexes on frequently queried fields (license_key, customer_email, status combinations)
- Unique constraints where needed (license key uniqueness, activation uniqueness)
- Foreign keys with CASCADE deletes to maintain data integrity

The `unique_together` constraint on Activation (license, instance_id, is_active) ensures we can't have duplicate active activations, but allows historical records when deactivated.

## Trade-offs and Decisions

### Multi-Tenancy: Shared Database vs Separate Databases

I went with a shared database approach where brand isolation is enforced at the application level. Each license key is tied to a brand, and queries are scoped accordingly.

**Why this approach:**
- Simpler to operate (one database to manage, backup, monitor)
- Easier to do cross-brand queries when needed (US6)
- Lower infrastructure costs
- Django ORM makes it straightforward

**Trade-offs:**
- Need to be careful with queries to avoid data leakage (but Django's ORM helps here)
- All brands share the same database resources (could be an issue at very large scale)
- Schema changes affect all brands

**Alternative considered:** Separate databases per brand. This would give stronger isolation but makes cross-brand queries much harder and increases operational complexity. For this use case, application-level isolation is sufficient.

### Authentication: API Keys vs OAuth/JWT

I used simple API key authentication for brands and license key authentication for end-users.

**Why this approach:**
- Simple to implement and understand
- No token expiration to manage
- Works well for server-to-server communication (brand systems)
- License keys are already customer-facing, so using them for auth makes sense

**Trade-offs:**
- API keys are long-lived (if compromised, need manual rotation)
- No built-in rate limiting per key (would need to add middleware)
- Less flexible than OAuth for future integrations

**Alternative considered:** OAuth 2.0 with JWT tokens. More secure and flexible, but adds complexity. For an internal service between brand systems and the license service, API keys are simpler and sufficient. Could upgrade later if needed.

### Seat Management: Implemented vs Designed-Only

I fully implemented seat management (max_seats on licenses, activation tracking, seat limits enforced).

**Why implement it:**
- It's a core requirement for many products
- The data model needed it anyway (max_seats field)
- The logic isn't that complex
- Better to show a complete feature than a half-implemented one

**Trade-offs:**
- Took more time, but demonstrates full understanding
- Some products might not need seats, but having the field optional handles that

### License Key Format: Human-Readable vs UUID

I went with a human-readable format like "GHX6-889J-WUIE-02R2" instead of raw UUIDs.

**Why this approach:**
- Easier for customers to type/communicate
- Still unique and hard to guess
- Better UX when customers need to enter keys

**Trade-offs:**
- Slightly more complex generation logic
- Need to ensure uniqueness (retry logic in place)

**Alternative considered:** Just use UUIDs. Simpler but worse UX. The generation overhead is minimal.

### Error Handling: Custom Handler vs Default

I implemented a custom exception handler that provides consistent error responses.

**Why this approach:**
- Consistent API responses make integration easier
- Can log errors with proper context
- Better for debugging production issues

**Trade-offs:**
- More code to maintain
- Need to ensure all exceptions are handled properly

### Scaling Considerations

**Current design supports:**
- Horizontal scaling (stateless API, can run multiple instances)
- Database read replicas (Django supports this)
- Caching layer (could add Redis for frequently accessed license keys)

**What would need to change at scale:**
- Add caching layer for license key lookups (very frequent operation)
- Consider read replicas for status checks
- Add rate limiting per API key
- Database connection pooling (already handled by Django)
- Consider event-driven architecture for license updates (currently synchronous)

**Migration path:**
The current design doesn't lock us into anything. We could add caching, move to microservices, or add async processing without major rewrites. The models and API contracts are stable.

## How Solution Satisfies Each User Story

### US1: Brand can provision a license ✅ **FULLY IMPLEMENTED**

**Endpoint:** `POST /api/brand/licenses/`

This is fully implemented. Brands can:
- Create a new license key for a customer email
- Create multiple product licenses in one request
- Get back the license key to send to the customer

The system handles the scenario from the requirements:
1. New RankMath purchase → Creates license key #1 with RankMath license
2. Content AI addon purchase → Adds Content AI license to existing license key #1
3. WP Rocket purchase → Creates new license key #2 (different brand)

The implementation uses `get_or_create` for license keys, so if a brand provisions licenses for the same email twice, it reuses the existing key. This prevents duplicate keys.

**Example request:**
```json
{
  "customer_email": "user@example.com",
  "products": [
    {
      "slug": "rankmath",
      "expiration_date": "2025-12-31T23:59:59",
      "max_seats": 5
    }
  ]
}
```

**Response includes:** license_key, customer_email, brand, licenses array, and created flag.

### US2: Brand can change license lifecycle ✅ **FULLY IMPLEMENTED**

**Endpoint:** `PATCH /api/brand/licenses/{license_id}/lifecycle/`

Fully implemented with support for:
- **Renew**: Extends expiration date (requires new expiration_date in request)
- **Suspend**: Sets status to suspended (license becomes invalid)
- **Resume**: Sets status back to valid (if currently suspended)
- **Cancel**: Sets status to cancelled (permanent)

The implementation validates:
- Brand owns the license (can't modify other brands' licenses)
- Current license state allows the action (e.g., can't resume a cancelled license)
- Renew action requires expiration_date parameter

**Example request:**
```json
{
  "action": "suspend"
}
```

### US3: End-user product can activate a license ✅ **FULLY IMPLEMENTED**

**Endpoint:** `POST /api/product/activate/`

Fully implemented with:
- Instance-based activation (site URL, host, machine ID, etc.)
- Seat limit enforcement (if max_seats is set on license)
- Duplicate activation handling (returns existing activation if already activated for that instance)
- Returns remaining seats count

The system checks:
- License exists and is valid (not expired, not suspended/cancelled)
- Seat availability (if max_seats is set)
- Prevents duplicate activations for same instance

**Example request:**
```json
{
  "instance_id": "https://example.com",
  "product_slug": "rankmath"
}
```

**Response includes:** activation_id, instance_id, product name, activated_at timestamp, and remaining_seats.

### US4: User can check license status ✅ **FULLY IMPLEMENTED**

**Endpoint:** `GET /api/product/check/`

Fully implemented. Returns:
- License key information
- Customer email and brand
- All licenses associated with the key
- For each license: status, expiration, max_seats, active_seats, remaining_seats

This gives end-user products everything they need to:
- Validate the license is still good
- Show what products are available
- Display seat usage information

**Response format:**
```json
{
  "status": "success",
  "license_key": "GHX6-889J-WUIE-02R2",
  "customer_email": "user@example.com",
  "brand": "RankMath",
  "licenses": [
    {
      "product_slug_read": "rankmath",
      "status": "valid",
      "expiration_date": "2025-12-31T23:59:59Z",
      "max_seats": 5,
      "active_seats": 2,
      "remaining_seats": 3
    }
  ]
}
```

### US5: End-user product or customer can deactivate a seat ✅ **FULLY IMPLEMENTED**

**Endpoint:** `POST /api/product/deactivate/`

Fully implemented. Allows deactivating a specific activation to free up a seat. Useful when:
- Customer moves to a new site
- Customer wants to free a seat for another instance
- Plugin/app is uninstalled

The implementation:
- Finds the active activation for the instance
- Marks it as inactive
- Updates deactivated_at timestamp
- Returns updated seat counts

**Example request:**
```json
{
  "instance_id": "https://oldsite.com",
  "product_slug": "rankmath"
}
```

### US6: Brands can list licenses by customer email across all brands ✅ **FULLY IMPLEMENTED**

**Endpoint:** `GET /api/brand/licenses/by-email/?email=user@example.com`

Fully implemented. This is the cross-brand query capability. Brands can:
- Query by customer email
- Get all licenses across ALL brands (not just their own)
- Useful for customer support scenarios

The implementation:
- Only accessible to brands (X-API-Key auth required)
- Returns licenses from all brands for the given email
- Groups results by brand for clarity

**Security note:** This is intentionally restricted to brand systems only. End-users cannot access this endpoint (they use the check endpoint which only shows their own licenses).

## Summary of Implementation Status

- **US1**: ✅ Fully implemented
- **US2**: ✅ Fully implemented (optional, but completed)
- **US3**: ✅ Fully implemented
- **US4**: ✅ Fully implemented
- **US5**: ✅ Fully implemented (optional, but completed)
- **US6**: ✅ Fully implemented

All core requirements (US1, US3, US4, US6) are fully implemented. The optional stories (US2, US5) are also complete.

## How to Run Locally

### Prerequisites

- Docker and Docker Compose installed
- OR Python 3.9+ and PostgreSQL 15+ if running locally

### Option 1: Using Docker (Recommended)

This is the easiest way to get started. Everything is containerized.

1. **Start the services:**
   ```bash
   docker-compose up -d
   ```
   This starts PostgreSQL and the Django web server.

2. **Run migrations:**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

3. **Set up test data:**
   ```bash
   docker-compose exec web python manage.py setup_test_data
   ```
   This creates RankMath and WP Rocket brands with products and prints the API keys.

4. **Access the service:**
   - API: http://localhost:8000
   - Swagger docs: http://localhost:8000/docs/
   - Admin panel: http://localhost:8000/admin/ (create superuser first if needed)

5. **View logs:**
   ```bash
   docker-compose logs -f web
   ```

### Option 2: Local Development

If you prefer running without Docker:

1. **Set up PostgreSQL:**
   - Install PostgreSQL 15+
   - Create database: `createdb license_service`
   - Create user (or use existing postgres user)

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   Create a `.env` file or set environment variables:
   ```
   DB_HOST=localhost
   DB_NAME=license_service
   DB_USER=postgres
   DB_PASSWORD=your_password
   DB_PORT=5432
   DEBUG=True
   SECRET_KEY=your-secret-key-here
   ```

5. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

6. **Set up test data:**
   ```bash
   python manage.py setup_test_data
   ```

7. **Run server:**
   ```bash
   python manage.py runserver
   ```

### Testing the API

Once the service is running, here are some sample requests to test:

**1. Provision a license (US1):**
```bash
curl -X POST http://localhost:8000/api/brand/licenses/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: rankmath-api-key-sgxOdIvSv-_BBnTBfRQc3w" \
  -d '{
    "customer_email": "john@example.com",
    "products": [
      {
        "slug": "rankmath",
        "expiration_date": "2025-12-31T23:59:59",
        "max_seats": 5
      }
    ]
  }'
```

Save the `license_key` from the response for next steps.

**2. Add product to existing key (US1):**
```bash
curl -X POST http://localhost:8000/api/brand/licenses/{license_key}/add-product/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: rankmath-api-key-sgxOdIvSv-_BBnTBfRQc3w" \
  -d '{
    "product_slug": "content-ai",
    "expiration_date": "2025-12-31T23:59:59",
    "max_seats": 3
  }'
```

**3. Activate license (US3):**
```bash
curl -X POST http://localhost:8000/api/product/activate/ \
  -H "Content-Type: application/json" \
  -H "X-License-Key: {license_key_from_step_1}" \
  -d '{
    "instance_id": "https://example.com",
    "product_slug": "rankmath"
  }'
```

**4. Check license status (US4):**
```bash
curl -X GET http://localhost:8000/api/product/check/ \
  -H "X-License-Key: {license_key_from_step_1}"
```

**5. Update license lifecycle (US2):**
```bash
curl -X PATCH http://localhost:8000/api/brand/licenses/{license_id}/lifecycle/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: rankmath-api-key-sgxOdIvSv-_BBnTBfRQc3w" \
  -d '{
    "action": "suspend"
  }'
```

**6. List licenses by email (US6):**
```bash
curl -X GET "http://localhost:8000/api/brand/licenses/by-email/?email=john@example.com" \
  -H "X-API-Key: rankmath-api-key-sgxOdIvSv-_BBnTBfRQc3w"
```

**7. Deactivate seat (US5):**
```bash
curl -X POST http://localhost:8000/api/product/deactivate/ \
  -H "Content-Type: application/json" \
  -H "X-License-Key: {license_key_from_step_1}" \
  -d '{
    "instance_id": "https://example.com",
    "product_slug": "rankmath"
  }'
```

### Test Credentials

After running `setup_test_data`, you'll get API keys printed to the console. The default ones are:
- **RankMath API Key**: `rankmath-api-key-sgxOdIvSv-_BBnTBfRQc3w` (or generated)
- **WP Rocket API Key**: `wprocket-api-key-T3nmHuBuh30dT5zP872JWw` (or generated)

Use these in the `X-API-Key` header for brand endpoints.

For product endpoints, use the `license_key` returned from the provision endpoint in the `X-License-Key` header.

### Health Check

Test that the service is running:
```bash
curl http://localhost:8000/api/health/
```

Should return:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

## Known Limitations and Next Steps

### Current Limitations

**1. No Rate Limiting**
The API doesn't have rate limiting per API key or license key. In production, you'd want to add this to prevent abuse. Could use Django middleware or a service like Redis for rate limiting.

**2. No Caching Layer**
License key lookups happen on every request. For high-traffic scenarios, adding Redis caching for frequently accessed license keys would improve performance significantly.

**3. Synchronous Operations**
All operations are synchronous. For high-volume scenarios, you might want async processing for things like license provisioning (though the current approach is simpler and works fine for most cases).

**4. No Webhook Support**
Brand systems can't subscribe to license events (like when a license is activated or expires). This would be useful for keeping brand systems in sync.

**5. Limited Audit Trail**
We log operations, but there's no detailed audit log table. If you need to track "who changed what when" for compliance, you'd want to add an audit log model.

**6. No Bulk Operations**
Can't provision multiple customers at once or bulk update licenses. For large migrations, you'd need to add bulk endpoints.

**7. API Key Rotation**
No built-in mechanism for rotating API keys. Currently requires manual database updates. Could add an endpoint for brands to rotate their keys.

**8. No License Key Versioning**
License keys are immutable. If you need to invalidate and regenerate keys (security incident), you'd need to add versioning or a revocation mechanism.

### What's Missing (But Not Critical)

**Tests**: The codebase doesn't have unit or integration tests. For production, you'd want:
- Unit tests for models and business logic
- Integration tests for API endpoints
- Tests for edge cases (expired licenses, seat limits, etc.)

**CI/CD**: No automated testing or deployment pipeline. Would be good to add:
- Linter checks (flake8, black)
- Test suite on PRs
- Automated deployments

**Monitoring**: Basic logging is in place, but no metrics collection. For production, you'd want:
- Metrics for API response times
- Error rate tracking
- License activation rates
- Database query performance

**Documentation**: Swagger docs are available, but could add:
- More detailed API documentation
- Integration guides for brand systems
- Troubleshooting guides

### Next Steps for Production

**Short-term (Before Launch):**
1. Add comprehensive test suite
2. Set up CI/CD pipeline
3. Add rate limiting
4. Implement caching layer (Redis)
5. Add monitoring and alerting (Prometheus/Grafana or similar)
6. Security audit and penetration testing

**Medium-term (Post-Launch):**
1. Add webhook support for license events
2. Implement audit logging
3. Add bulk operations endpoints
4. Build admin dashboard for operations team
5. Add license key versioning/revocation

**Long-term (Scale):**
1. Consider microservices architecture if single service becomes bottleneck
2. Add read replicas for status check endpoints
3. Implement event-driven architecture for license updates
4. Add multi-region support if needed
5. Consider GraphQL API for more flexible queries

### Design Decisions That Could Change

**Shared Database**: If we need stronger isolation or compliance requirements, could move to separate databases per brand. Would require more operational overhead but better isolation.

**API Key Auth**: Could upgrade to OAuth 2.0 if we need more sophisticated auth (token refresh, scopes, etc.). Current approach works fine for server-to-server.

**Synchronous Processing**: Could move to async/event-driven if we need to handle very high volumes or want to decouple brand systems from license service.

The good news is that the current architecture doesn't lock us into any of these decisions. We can evolve the system as needs change without major rewrites.

