# Alembic Database Migrations

This project uses **Alembic** for managing database schema migrations with SQLAlchemy.

## 📋 Overview

Alembic is a lightweight database migration tool for SQLAlchemy that allows you to:
- Track schema changes over time
- Apply/rollback migrations easily
- Share migrations across team members
- Maintain database consistency

## 🚀 Getting Started

### Prerequisites
```bash
# Alembic is already installed
pip install alembic  # If needed
```

### Configuration Files
- **alembic.ini** - Main Alembic configuration
- **alembic/env.py** - Migration environment setup
- **alembic/script.py.mako** - Migration script template
- **alembic/versions/** - Actual migration files

## 🔧 Configuration

### Database URL
The migration system reads from your `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost/navdb
```

The URL is automatically converted to async format:
- `postgresql://` → `postgresql+asyncpg://`
- Removes `sslmode` and other psycopg2-only parameters

## 📝 Creating Migrations

### Automatic Generation (When DB Connected)

Generate migrations automatically from model changes:

```bash
# Create a migration based on changes in models
alembic revision --autogenerate -m "Add new_column to users"
```

The generated file will be in `alembic/versions/` with timestamp and slug.

### Manual Migration

Create an empty migration template:

```bash
alembic revision -m "Create new table"
```

Then edit the generated file to add your SQL operations.

### Initial Migration (Already Done)

The initial migration (`001_initial_schema.py`) creates all tables with:
- All columns with proper types
- Primary keys and foreign keys
- Unique constraints
- Check constraints
- Database indexes
- Spatial indexes for geometry columns
- Automatic timestamps with server defaults

## 🔄 Applying Migrations

### Apply All Pending Migrations

```bash
alembic upgrade head
```

### Apply Specific Migration

```bash
alembic upgrade <revision_id>
```

Example:
```bash
alembic upgrade 001_initial_schema
```

### Apply N Migrations

```bash
alembic upgrade +2  # Apply next 2 migrations
```

## ⏮️ Rolling Back Migrations

### Rollback Latest Migration

```bash
alembic downgrade -1
```

### Rollback to Specific Revision

```bash
alembic downgrade <revision_id>
```

### Rollback All Migrations

```bash
alembic downgrade base
```

## 📊 Checking Migration Status

### Current Revision

```bash
alembic current
```

Shows which migration is currently applied.

### Migration History

```bash
alembic history
```

Shows all migrations in chronological order.

### Migration Branches

```bash
alembic branches
```

Shows any migration branches (if using branch labels).

### Heads

```bash
alembic heads
```

Shows the latest revision(s).

## 🔍 Creating and Editing Migrations

### Auto-Generated Migration Example

When you run `alembic revision --autogenerate`, a file is created like:

```python
"""Add user_email column

Revision ID: 20260203120000_add_user_email
Revises: 001_initial_schema
Create Date: 2026-02-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260203120000_add_user_email'
down_revision = '001_initial_schema'

def upgrade():
    op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
    op.create_unique_constraint('uq_users_email', 'users', ['email'])

def downgrade():
    op.drop_constraint('uq_users_email', 'users')
    op.drop_column('users', 'email')
```

### Manual Migration Template

```python
"""Description of changes

Revision ID: <revision_id>
Revises: <previous_revision>
Create Date: <timestamp>

"""
from alembic import op
import sqlalchemy as sa

revision = '<revision_id>'
down_revision = '<previous_revision>'

def upgrade():
    # Add changes here
    op.create_table(
        'new_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    # Reverse changes here
    op.drop_table('new_table')
```

## 🛠️ Common Operations

### Add Column

```python
def upgrade():
    op.add_column('table_name', 
        sa.Column('new_column', sa.String(50), nullable=False, server_default='default'))

def downgrade():
    op.drop_column('table_name', 'new_column')
```

### Drop Column

```python
def upgrade():
    op.drop_column('table_name', 'old_column')

def downgrade():
    op.add_column('table_name',
        sa.Column('old_column', sa.String(50), nullable=True))
```

### Rename Column

```python
def upgrade():
    op.alter_column('table_name', 'old_name', new_column_name='new_name')

def downgrade():
    op.alter_column('table_name', 'new_name', new_column_name='old_name')
```

### Add Index

```python
def upgrade():
    op.create_index('ix_table_column', 'table_name', ['column_name'])

def downgrade():
    op.drop_index('ix_table_column', table_name='table_name')
```

### Add Constraint

```python
def upgrade():
    op.create_unique_constraint('uq_table_column', 'table_name', ['column_name'])

def downgrade():
    op.drop_constraint('uq_table_column', 'table_name')
```

### Create Table

```python
def upgrade():
    op.create_table(
        'new_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('new_table')
```

## 📂 Migration File Structure

Generated migrations follow this naming pattern:

```
YYYYMMDD_HHMMSS_<revision_id>_<description>.py
```

Example:
```
20260203_120000_001_initial_schema.py
20260203_130000_add_user_roles.py
```

## 🔐 Best Practices

### 1. Write Reversible Migrations

Both `upgrade()` and `downgrade()` should be functional:

```python
# ✅ Good - Reversible
def upgrade():
    op.add_column('users', sa.Column('age', sa.Integer()))

def downgrade():
    op.drop_column('users', 'age')

# ❌ Bad - Cannot downgrade
def upgrade():
    op.execute("UPDATE users SET name = UPPER(name)")

def downgrade():
    pass  # Can't undo uppercase
```

### 2. Test Migrations

Before committing, test both upgrade and downgrade:

```bash
# Apply migration
alembic upgrade head

# Test application works

# Rollback
alembic downgrade -1

# Upgrade again
alembic upgrade head
```

### 3. Use Descriptive Names

```bash
✅ alembic revision -m "Add email column to users table"
❌ alembic revision -m "Add column"
```

### 4. One Logical Change Per Migration

Keep migrations focused:

```bash
✅ Create separate migrations for:
  - Adding new table
  - Adding columns to table
  - Adding indexes
  
❌ Don't combine unrelated changes in one migration
```

### 5. Handle Data Migrations Carefully

```python
def upgrade():
    # 1. Add column
    op.add_column('users', sa.Column('new_status', sa.String(50)))
    
    # 2. Migrate data
    op.execute("UPDATE users SET new_status = 'active' WHERE status = 1")
    
    # 3. Make NOT NULL if needed
    op.alter_column('users', 'new_status', nullable=False)

def downgrade():
    op.drop_column('users', 'new_status')
```

### 6. Use Server Defaults

```python
# ✅ Good - Database handles default
sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())

# ❌ Avoid - Only Python side has default
sa.Column('created_at', sa.DateTime(), default=datetime.now)
```

## 🔍 Troubleshooting

### Migration File Not Found

```
ERROR: Can't find sqlalchemy module
```

**Solution:** Ensure models are importable from alembic directory:

```bash
# From project root
alembic revision --autogenerate -m "..."
```

### Database Connection Error

```
TypeError: connect() got an unexpected keyword argument 'sslmode'
```

**Solution:** Ensure DATABASE_URL is set and async URL is clean:

```bash
# Check .env
cat .env | grep DATABASE_URL

# URL should start with postgresql://
# Will be converted to postgresql+asyncpg:// automatically
```

### Migration Already Applied

```
Can't locate revision identified by ...
```

**Solution:** Check current revision:

```bash
alembic current
alembic history
```

### Conflicting Migrations

If two branches create conflicting migrations:

```bash
# Check heads
alembic heads

# Merge manually or use:
alembic merge <rev1> <rev2> -m "Merge branches"
```

## 📚 Useful Commands Reference

```bash
# Check current applied migration
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic heads

# Create new migration (auto-generate)
alembic revision --autogenerate -m "message"

# Create empty migration
alembic revision -m "message"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback all migrations
alembic downgrade base

# Downgrade to specific revision
alembic downgrade <revision>

# Show details of a migration
alembic show <revision>

# Stamp database with specific revision (without applying)
alembic stamp <revision>

# Initialize Alembic in existing project
alembic init alembic
```

## 🚀 Integration with CI/CD

### Automatic Migration on Deployment

Add to your deployment script:

```bash
#!/bin/bash

# Upgrade database to latest schema
python -c "
import asyncio
from alembic import command
from alembic.config import Config

alembic_cfg = Config('alembic.ini')
command.upgrade(alembic_cfg, 'head')
"
```

### Pre-flight Checks

```bash
#!/bin/bash

# Check if migrations are pending
alembic current | grep -q "head" || {
    echo "Pending migrations found!"
    exit 1
}
```

## 📖 Resources

- [Alembic Official Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy ORM Documentation](https://docs.sqlalchemy.org/en/20/orm/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## 🔒 Version Control

Always commit migration files:

```bash
git add alembic/versions/*.py
git commit -m "Add database migration: ..."
```

## 🎯 Workflow Example

### Day-to-Day Development

```bash
# 1. Update model
# Edit models/users.py - add new column

# 2. Create migration
alembic revision --autogenerate -m "Add email to users"

# 3. Review generated migration
cat alembic/versions/20260203_*.py

# 4. Test upgrade
alembic upgrade head

# 5. Test downgrade
alembic downgrade -1

# 6. Upgrade again for development
alembic upgrade head

# 7. Commit
git add alembic/versions/20260203_*.py
git commit -m "Add email column to users"

# 8. Push
git push
```

### Team Collaboration

```bash
# Pull latest migrations
git pull

# Apply new migrations from teammates
alembic upgrade head

# Continue working
```

## 📞 Support

If you encounter issues:

1. Check the migration file syntax
2. Verify database connectivity
3. Review alembic.ini configuration
4. Check alembic/env.py settings
5. Run alembic history to see what's applied

---

**Alembic Configuration:** Async PostgreSQL with SQLAlchemy 2.0+  
**Initial Migration:** 001_initial_schema  
**Status:** ✅ Ready for use
