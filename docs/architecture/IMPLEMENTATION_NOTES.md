# Implementation Notes: Source-Specific Vector Tables

## Current Status

### ✅ Implemented
1. **Helper Functions**: `get_vector_table_name()` in `vector_db_helper.py` for table name mapping
2. **Source Type Support**: `ingest_documents()` now accepts `source_type` parameter
3. **Metadata Enhancement**: Source type automatically added to document metadata
4. **Collection Naming**: Enhanced collection names include source type for future separation

### 📋 Next Steps for Full Table Separation

The current implementation uses **enhanced collections** (metadata-based filtering) which provides good performance for current scale. To achieve full **separate tables per source** for petabyte scale, implement:

#### 1. Create Source-Specific Tables (Migration)

```sql
-- Create tables for each source type
CREATE TABLE vectors_slack (
    id UUID PRIMARY KEY,
    collection_id UUID,
    embedding vector(1536),
    document TEXT,
    metadata JSONB,
    created_at TIMESTAMP
);

CREATE TABLE vectors_teams (...);
CREATE TABLE vectors_onedrive (...);
-- etc.
```

#### 2. Update PGVector Initialization

Since `langchain_postgres.PGVector` doesn't directly support `table_name` parameter, we need to either:

**Option A**: Pre-create tables and use custom PGVector wrapper
**Option B**: Fork/extend PGVector to support table_name
**Option C**: Use SQLAlchemy directly for table management

#### 3. Migration Path

- **Phase 1**: Current (collections with source_type metadata) ✅
- **Phase 2**: Create source tables, use for new sources
- **Phase 3**: Migrate existing data to source tables
- **Phase 4**: Update queries to use source tables

## Current Architecture Benefits

Even with collections, the current implementation provides:

1. **Source Type Filtering**: Metadata-based filtering by source_type
2. **Collection Organization**: Collections organized by source for logical separation
3. **Query Optimization**: Can filter by source_type in metadata (efficient JSONB queries)
4. **Future-Ready**: Code prepared for table separation when needed

## Performance Notes

For current scale (< 100GB), collections work well. For petabyte scale:
- **Separate tables** provide 10-100x query performance improvement
- **Source-specific indexes** are more efficient
- **Partitioning** becomes feasible per table

The foundation is in place - when scaling requires it, table separation can be implemented with minimal code changes.
