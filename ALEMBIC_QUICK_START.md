# Alembic Quick Reference

## Setup Complete ✅

Your Alembic database migration system is configured and ready to use!

### Files Created

```
✅ alembic/
   ├── env.py                          # Migration environment
   ├── script.py.mako                  # Migration template
   ├── versions/
   │   └── 001_initial_schema.py       # Initial migration
   ├── README
   └── alembic.ini                     # Configuration file
```

## Quick Commands

### View Migration Status

```bash
# Show current migration
alembic current

# Show all migrations
alembic history

# Show pending migrations  
alembic heads
```

### Apply Migrations (When DB Ready)

```bash
# Apply all pending migrations
alembic upgrade head

# Apply specific migration
alembic upgrade 001_initial_schema

# Apply next N migrations
alembic upgrade +1
```

### Rollback Migrations

```bash
# Rollback latest
alembic downgrade -1

# Rollback all
alembic downgrade base

# Rollback to specific migration
alembic downgrade 001_initial_schema
```

### Create New Migrations

```bash
# Auto-generate from model changes (requires DB connection)
alembic revision --autogenerate -m "Description"

# Create empty migration
alembic revision -m "Description"
```

## Initial Migration

The **001_initial_schema** migration creates:

- ✅ 7 tables with proper relationships
- ✅ All columns with correct types  
- ✅ Foreign key constraints
- ✅ Unique constraints (prevent duplicates)
- ✅ Check constraints (data validation)
- ✅ Database indexes (performance)
- ✅ Spatial indexes for geometry (PostGIS)
- ✅ Automatic timestamps

## Step-by-Step Usage

### 1. Prepare Database

```bash
# Ensure PostgreSQL is running
# Ensure PostGIS extension is enabled (for geometry types)

psql -U postgres
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE DATABASE navigation_db;
```

### 2. Set Environment Variable

```bash
export DATABASE_URL="postgresql://user:password@localhost/navigation_db"
```

### 3. Apply Initial Migration

```bash
cd /Users/rodynaamr/PycharmProjects/navigation-service

# Apply all migrations (just the initial one for now)
alembic upgrade head
```

### 4. Verify Database

```bash
# Check current migration
alembic current

# Should output: 001_initial_schema
```

### 5. Start Using Application

```bash
# Run your FastAPI app
python main.py
```

## Making Changes

### When You Update Models

```bash
# 1. Update models/your_model.py
# (add new column, change type, add relationship, etc.)

# 2. Generate migration
alembic revision --autogenerate -m "Add new_column to table"

# 3. Review the generated file
cat alembic/versions/*.py

# 4. Apply migration
alembic upgrade head

# 5. Test your changes

# 6. Commit to git
git add alembic/versions/*.py
git commit -m "Add migration: ..."
```

## Important Notes

### Database Connection
- Configure `DATABASE_URL` in `.env`
- Format: `postgresql://user:password@host/database`
- Will auto-convert to `postgresql+asyncpg://` for async

### Migrations Are Immutable
- Never edit an already-applied migration
- If you need changes, create a new migration
- Use `alembic downgrade` first if you haven't shared yet

### Team Workflow
```bash
# Pull latest migrations from team
git pull

# Apply new migrations
alembic upgrade head

# Continue developing
```

## Troubleshooting

### "Can't find migration" error
```bash
# Ensure you're in the right directory
cd /Users/rodynaamr/PycharmProjects/navigation-service

# Check migration history
alembic history
```

### Database connection errors
```bash
# Verify DATABASE_URL is set
echo $DATABASE_URL

# Ensure PostgreSQL is running
psql -U postgres -c "SELECT 1"
```

### "No changes detected" on autogenerate
```bash
# Alembic couldn't detect changes
# Check if models are imported in env.py
# Verify model changes are syntactically correct
```

## Configuration Files

### alembic.ini
- Main Alembic configuration
- Sets script location, template format, logging
- **Don't edit unless you know what you're doing**

### alembic/env.py  
- Handles async PostgreSQL configuration
- Imports models for autogenerate
- Cleans database URL (removes incompatible params)
- **Already configured, minimal editing needed**

## Learn More

📖 Full documentation: [ALEMBIC_USAGE.md](ALEMBIC_USAGE.md)

## Ready to Start? 🚀

```bash
# 1. Ensure database is ready
export DATABASE_URL="postgresql://user:password@localhost/db"

# 2. Check status
alembic current

# 3. Apply migrations when DB is ready
alembic upgrade head

# 4. Start developing!
python main.py
```

---

**Status:** ✅ Alembic configured for async PostgreSQL  
**Initial Migration:** ✅ 001_initial_schema ready  
**Database:** 🔄 Waiting for connection details  
**Last Updated:** February 3, 2026
