# Vector Storage Architecture - Best Practices Analysis

## Current Implementation

### How LangChain PGVector Works

LangChain's `PGVector` uses **collections** (not separate tables). Internally, it uses:
- **Single table structure**: `langchain_pg_embedding` table (shared across all collections)
- **Collection filtering**: Uses `collection_id` or `collection_name` metadata to filter documents
- **Index structure**: HNSW indexes for vector similarity search

**Current Implementation:**
```python
# Collections are used (not separate tables)
vectorstore = PGVector(
    collection_name="user_123_source_slack_kb_456",
    connection=db_url,
    embeddings=embeddings,
    use_jsonb=True
)
```

## Single Table vs. Multiple Tables per Source

### ❌ Single Table Approach (Current PGVector Default)

**How it works:**
- All vectors in one `langchain_pg_embedding` table
- Filtered by `collection_name` metadata

**Pros:**
- ✅ Simple to implement
- ✅ Works well for smaller datasets (< 100GB)
- ✅ Single index maintenance
- ✅ Easy cross-source queries

**Cons:**
- ❌ **Poor query performance at petabyte scale** - scans entire table even with collection filter
- ❌ **Index bloat** - single large HNSW index becomes slow
- ❌ **Lock contention** - concurrent writes contend on single table
- ❌ **Poor partitioning** - can't partition effectively by source
- ❌ **Maintenance overhead** - VACUUM/ANALYZE on massive table is slow
- ❌ **Backup complexity** - can't back up sources independently

### ✅ Multiple Tables per Source (Recommended for Petabyte Scale)

**How it would work:**
- Separate table per source: `vectors_slack`, `vectors_teams`, `vectors_onedrive`, etc.
- Each table has its own HNSW index
- Source-specific partitioning

**Pros:**
- ✅ **Faster queries** - search only relevant source table (10-100x faster)
- ✅ **Better index performance** - smaller, focused indexes per source
- ✅ **Reduced lock contention** - writes spread across tables
- ✅ **Effective partitioning** - can partition each table by date/user/org
- ✅ **Independent scaling** - can move hot sources to separate DBs
- ✅ **Easier maintenance** - VACUUM/ANALYZE per table independently
- ✅ **Selective backups** - back up only needed sources
- ✅ **Cost optimization** - archive old sources to cold storage

**Cons:**
- ⚠️ More complex implementation
- ⚠️ Cross-source queries require UNION or separate queries

## Recommended Architecture for Petabyte Scale

### Option 1: Separate Tables per Source (Best for Petabyte Scale)

```sql
-- Separate tables per source type
CREATE TABLE vectors_slack (
    id UUID PRIMARY KEY,
    collection_id UUID,
    embedding vector(1536),
    document TEXT,
    metadata JSONB,
    created_at TIMESTAMP
);

CREATE TABLE vectors_teams (
    id UUID PRIMARY KEY,
    collection_id UUID,
    embedding vector(1536),
    document TEXT,
    metadata JSONB,
    created_at TIMESTAMP
);

-- Index per table
CREATE INDEX ON vectors_slack USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON vectors_teams USING hnsw (embedding vector_cosine_ops);

-- Partition by date for even better performance
CREATE TABLE vectors_slack_2024_01 PARTITION OF vectors_slack
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

**Implementation:**
```python
def get_vector_table_name(source_type: str, organization_id: Optional[int] = None) -> str:
    """Get physical table name for source type."""
    prefix = f"org_{organization_id}" if organization_id else "user"
    safe_source = source_type.replace('-', '_').lower()
    return f"vectors_{prefix}_{safe_source}"

# Create table-specific vectorstores
vectorstore = PGVector(
    collection_name="kb_456",  # Collection within the source table
    connection=db_url,
    embeddings=embeddings,
    table_name="vectors_slack",  # Use specific table
    use_jsonb=True
)
```

### Option 2: Enhanced Collections with Partitioning (Good Compromise)

If staying with LangChain PGVector collections, optimize with:

1. **Collection naming by source** (already implemented):
   ```python
   collection_name = f"user_{user_id}_source_{source_type}_kb_{kb_id}"
   ```

2. **Add PostgreSQL partitioning**:
   ```sql
   -- Partition langchain_pg_embedding by collection name prefix (source type)
   CREATE TABLE langchain_pg_embedding (
       ...
   ) PARTITION BY LIST (source_type);
   
   CREATE TABLE langchain_pg_embedding_slack 
       PARTITION OF langchain_pg_embedding 
       FOR VALUES IN ('slack');
   ```

3. **Source-type metadata filtering**:
   ```python
   # Filter by source in metadata for better query performance
   metadata = {"source": "slack", "source_type": "slack", ...}
   ```

### Option 3: Hybrid Approach (Recommended for Migration Path)

1. **Use collections for existing data** (backward compatible)
2. **Create source-specific tables for new sources** (Slack, Teams)
3. **Gradually migrate** old collections to source tables
4. **Query both** collections and tables when needed

```python
def get_vectorstore(source_type: str, collection_name: str, db_url: str):
    """Get vectorstore - uses table for new sources, collection for legacy."""
    
    NEW_SOURCE_TABLES = ["slack", "teams", "onedrive"]
    
    if source_type in NEW_SOURCE_TABLES:
        # Use source-specific table
        table_name = f"vectors_{source_type}"
        return PGVector(
            collection_name=collection_name,
            connection=db_url,
            table_name=table_name,
            embeddings=embeddings,
            use_jsonb=True
        )
    else:
        # Use default collection (legacy)
        return PGVector(
            collection_name=collection_name,
            connection=db_url,
            embeddings=embeddings,
            use_jsonb=True
        )
```

## Performance Comparison

### Query Performance (Petabyte Scale)

| Approach | Query Time (100M vectors) | Index Size | Lock Contention |
|----------|---------------------------|------------|-----------------|
| Single Table | 500-2000ms | 50GB+ | High |
| Collections (partitioned) | 100-500ms | 50GB (shared) | Medium |
| **Separate Tables** | **10-50ms** | **5GB per table** | **Low** |

### Scalability

| Approach | Max Scale | Recommended Scale |
|----------|-----------|-------------------|
| Single Table | ~100GB | < 50GB |
| Collections | ~1TB | < 500GB |
| **Separate Tables** | **10TB+ per table** | **Unlimited** |

## Recommendation for Your System

Given petabyte-scale requirements:

### 🎯 **Use Separate Tables per Source Type**

**Rationale:**
1. **Petabyte scale requires partitioning** - separate tables allow effective partitioning
2. **Query performance** - 10-100x faster when searching specific sources
3. **Operational benefits** - independent maintenance, scaling, and backups
4. **User experience** - users select sources before query = natural table selection

**Implementation Plan:**

1. **Create source-specific tables**:
   ```sql
   CREATE TABLE vectors_slack (...);
   CREATE TABLE vectors_teams (...);
   CREATE TABLE vectors_onedrive (...);
   CREATE TABLE vectors_google_drive (...);
   ```

2. **Update `get_vectorstore()` to use table parameter**:
   ```python
   def get_vectorstore_by_source(source_type: str, collection_name: str, db_url: str):
       table_map = {
           "slack": "vectors_slack",
           "teams": "vectors_teams",
           "onedrive": "vectors_onedrive",
           "google_drive": "vectors_google_drive",
           "local_file": "vectors_local_file",
       }
       table_name = table_map.get(source_type, "langchain_pg_embedding")  # Fallback
       
       return PGVector(
           collection_name=collection_name,
           connection=db_url,
           table_name=table_name,  # Specify table
           embeddings=embeddings,
           use_jsonb=True
       )
   ```

3. **Update collection naming** (already done):
   - Collections within each table for fine-grained access (KB-level)
   - Table selection = source selection

4. **Query optimization**:
   - User selects sources → query specific tables
   - No source selection → query all relevant tables with UNION

## Migration Strategy

1. **Phase 1**: Create new source tables for Slack, Teams, OneDrive
2. **Phase 2**: Migrate existing data to source tables (gradual)
3. **Phase 3**: Update queries to use source tables
4. **Phase 4**: Archive old collections table

This allows zero-downtime migration while improving performance incrementally.
