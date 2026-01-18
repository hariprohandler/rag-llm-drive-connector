# Database Migrations

This directory contains database migration scripts for schema changes.

## Running Migrations

### Manual Migration Script

To add the `user_settings` table:

```bash
python migrations/add_user_settings_table.py
```

### Using Alembic (if configured)

If you have Alembic configured:

```bash
# Create a new migration
alembic revision --autogenerate -m "Add user_settings table"

# Apply migrations
alembic upgrade head
```

### Using SQLAlchemy create_all

The `init_db()` function in `app/models/base.py` will automatically create all tables defined in models, including the new `user_settings` table.

## Recent Migrations

### Migration: Add vector database configuration to user_settings

**Date**: 2026-01-18  
**Revision ID**: f5e6d7c8a9b0  
**Description**: Adds vector database configuration columns (`vector_db_url`, `vector_db_config`, `vector_db_enabled`) to `user_settings` table for user-configurable pgvector databases.

### Migration: Add institutional accounts (organizations)

**Date**: 2026-01-18  
**Revision ID**: acb0a7ee2ae  
**Description**: Adds institutional account support with organizations, members, groups, and document sharing. Includes:
- `organizations` table
- `organization_members` table (with roles)
- `organization_groups` table
- `organization_group_members` table (many-to-many)
- `organization_id` column added to `knowledge_bases`

## Migration: Add user_settings table

**Date**: 2026-01-06  
**Revision ID**: 43c3d5f14a36  
**Description**: Adds `user_settings` table to store user preferences including organization name.

### Schema

```sql
CREATE TABLE user_settings (
    id VARCHAR NOT NULL PRIMARY KEY,
    user_id VARCHAR NOT NULL UNIQUE,
    organization_name VARCHAR,
    preferences TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_settings_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE
);

CREATE INDEX idx_user_settings_user_id ON user_settings(user_id);
```

### Changes

- Added `UserSettings` model in `app/models/user_settings.py`
- Added manual migration script in `migrations/add_user_settings_table.py`
- Added Alembic migration in `migrations/versions/43c3d5f14a36_add_user_settings_table_for_.py`
- Updated `app/api/settings_routes.py` to use database instead of localStorage
- Updated `app/models/__init__.py` to export `UserSettings`
- Updated `migrations/env.py` to include UserSettings model for autogenerate
- Added Makefile target `migrate-user-settings` for manual migration

### Rollback

To rollback this migration:

**Using Alembic:**
```bash
alembic downgrade -1
```

**Manual SQL:**
```sql
DROP TABLE IF EXISTS user_settings CASCADE;
```

### Running the Migration

**Option 1: Using Alembic (Recommended)**
```bash
make migrate
# or
alembic upgrade head
```

**Option 2: Using Manual Script**
```bash
make migrate-user-settings
# or
python migrations/add_user_settings_table.py
```

**Option 3: Automatic (via init_db)**
The `init_db()` function will automatically create the table when the app starts if it doesn't exist.

