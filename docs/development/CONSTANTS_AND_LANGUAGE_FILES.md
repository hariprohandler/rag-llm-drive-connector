# Constants and Language Files Guide

This document explains the constants and language file organization following industry standards.

## Constants Module

### Location: `app/constants/`

Constants are organized by category into separate files:

```
app/constants/
├── __init__.py           # Exports all constants
├── source_types.py       # Source type enumerations
├── statuses.py           # Status enumerations (Connector, SyncJob, etc.)
├── defaults.py           # Default values (chunk_size, batch_size, etc.)
├── limits.py             # Application limits (max file size, etc.)
├── table_names.py        # Vector table name constants
└── collection_names.py   # Collection name prefix constants
```

### Usage

**Import constants:**
```python
from app.constants import SourceType, DefaultValues, TableNames, CollectionPrefix
from app.constants import ConnectorStatus, SyncJobStatus
```

**Use constants instead of hardcoded values:**
```python
# ❌ Bad
source_type = "slack"
chunk_size = 1000
batch_size = 200

# ✅ Good
from app.constants import SourceType, DefaultValues
source_type = SourceType.SLACK.value
chunk_size = DefaultValues.CHUNK_SIZE
batch_size = DefaultValues.INGESTION_BATCH_SIZE
```

## Language Files (i18n)

### Location: `app/locales/`

Language files follow i18n standards:

```
app/locales/
├── __init__.py           # Translation functions (t())
└── en/                   # English language
    ├── __init__.py
    └── messages.py       # All English messages
```

### Supported Languages

- `en` - English (default)
- Can be extended: `es`, `fr`, `de`, `ja`, etc.

### Usage

**Import translation function:**
```python
from app.locales import t
```

**Use messages instead of hardcoded strings:**
```python
# ❌ Bad
raise ValueError("User not found")
return {"message": "Operation completed successfully"}

# ✅ Good
from app.locales import t
raise ValueError(t('error.not_found.user'))
return {"message": t('success.operation.completed')}
```

**Message formatting:**
```python
# With parameters
error_msg = t('error.not_found', resource='Knowledge Base')
# Returns: "Knowledge Base not found"

# Without parameters
success_msg = t('success.operation.completed')
# Returns: "Operation completed successfully"
```

## Message Key Structure

Message keys follow hierarchical naming:

```
category.subcategory.key
```

**Examples:**
- `error.not_found.user` - User not found error
- `error.validation.required` - Field required validation
- `success.operation.completed` - Operation completed success
- `status.sync.processing` - Sync processing status
- `connector.slack` - Slack connector display name

## Constants Organization

### Source Types (`source_types.py`)

```python
from app.constants import SourceType

# Use enum instead of strings
if source_type == SourceType.SLACK.value:
    # Process Slack
```

### Default Values (`defaults.py`)

```python
from app.constants import DefaultValues

# Use constants for defaults
RecursiveCharacterTextSplitter(
    chunk_size=DefaultValues.CHUNK_SIZE,
    chunk_overlap=DefaultValues.CHUNK_OVERLAP
)
```

### Table Names (`table_names.py`)

```python
from app.constants import TableNames

# Get table name for source type
table_name = TableNames.get_table_name("slack")
# Returns: "vectors_slack"

# Get source type from table name
source_type = TableNames.get_source_type("vectors_slack")
# Returns: "slack"
```

### Status Enumerations (`statuses.py`)

```python
from app.constants import ConnectorStatus, SyncJobStatus

# Use enum instead of strings
connector.status = ConnectorStatus.CONNECTED
job.status = SyncJobStatus.COMPLETED
```

## Benefits

1. **Single Source of Truth**: Constants defined once, used everywhere
2. **Type Safety**: Enum prevents typos and invalid values
3. **Easy Updates**: Change value in one place, updates everywhere
4. **Internationalization**: Easy to add new languages
5. **Maintainability**: Clear organization and structure
6. **Testability**: Easy to mock constants in tests

## Migration Guide

### Replacing Hardcoded Strings

**Before:**
```python
if source_type == "slack":
    process_slack()
```

**After:**
```python
from app.constants import SourceType
if source_type == SourceType.SLACK.value:
    process_slack()
```

### Replacing Magic Numbers

**Before:**
```python
chunk_size = 1000
batch_size = 200
```

**After:**
```python
from app.constants import DefaultValues
chunk_size = DefaultValues.CHUNK_SIZE
batch_size = DefaultValues.INGESTION_BATCH_SIZE
```

### Replacing Hardcoded Messages

**Before:**
```python
raise ValueError("User not found")
return {"message": "Operation completed"}
```

**After:**
```python
from app.locales import t
raise ValueError(t('error.not_found.user'))
return {"message": t('success.operation.completed')}
```

## Best Practices

1. **Always use constants** instead of hardcoded values
2. **Use enums** for fixed sets of values (statuses, types)
3. **Use translation function** for all user-facing messages
4. **Document constants** with docstrings
5. **Group related constants** in same file
6. **Use descriptive names** for constants

## Adding New Constants

1. **Add to appropriate file** in `app/constants/`
2. **Export in `__init__.py`**
3. **Update code** to use new constant
4. **Add tests** for new constant
5. **Update documentation**

## Adding New Messages

1. **Add to `app/locales/en/messages.py`** with hierarchical key
2. **Use in code** via `t()` function
3. **Add translations** for other languages when needed
