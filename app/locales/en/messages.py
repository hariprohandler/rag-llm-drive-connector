"""English language messages for the application."""

# Message keys follow hierarchical naming: category.subcategory.key
# Example: error.validation.required, success.operation.completed

messages = {
    # Error Messages
    "error.validation.required": "Field is required",
    "error.validation.invalid_email": "Invalid email address",
    "error.validation.invalid_format": "Invalid format",
    
    "error.not_found": "{resource} not found",
    "error.not_found.user": "User not found",
    "error.not_found.connector": "Connector not found",
    "error.not_found.knowledge_base": "Knowledge base not found",
    "error.not_found.organization": "Organization not found",
    "error.not_found.document": "Document not found",
    
    "error.unauthorized": "Unauthorized access",
    "error.forbidden": "Access forbidden",
    "error.authentication.failed": "Authentication failed",
    "error.authentication.expired": "Authentication token expired",
    
    "error.database.connection": "Database connection failed",
    "error.database.query": "Database query failed",
    "error.database.transaction": "Transaction failed",
    
    "error.vector_db.compatibility": "Vector database compatibility check failed: {error}",
    "error.vector_db.connection": "Vector database connection test failed: {message}",
    "error.vector_db.pgvector_not_installed": "pgvector extension not found and could not be created",
    
    "error.ingestion.failed": "Document ingestion failed",
    "error.ingestion.empty_documents": "No documents to ingest",
    "error.ingestion.unsupported_format": "Unsupported file format: {format}",
    "error.ingestion.file_too_large": "File too large: {size}MB (max: {max}MB)",
    
    "error.llm.config_not_found": "No LLM configuration found. Please configure an API key in settings or add a user-specific LLM configuration.",
    "error.llm.api_key_decryption_failed": "Failed to decrypt API key for {provider}. This may happen if the encryption key changed. Please update your LLM configuration with a new API key. Original error: {error}",
    "error.llm.unsupported_provider": "Unsupported LLM provider: {provider}",
    
    "error.connector.connection_failed": "Failed to connect to {connector_type}",
    "error.connector.oauth_required": "OAuth authentication required for {connector_type}",
    "error.connector.not_connected": "Connector is not connected",
    "error.connector.already_connected": "Connector is already connected",
    
    "error.sync_job.creation_failed": "Failed to create sync job",
    "error.sync_job.not_found": "Sync job not found",
    "error.sync_job.cancellation_failed": "Failed to cancel sync job",
    
    "error.fine_tuning.job_not_found": "Fine-tuning job not found",
    "error.fine_tuning.creation_failed": "Failed to create fine-tuning job",
    "error.fine_tuning.invalid_data_source": "Invalid data source for fine-tuning",
    
    "error.organization.member_exists": "User is already a member of this organization",
    "error.organization.not_member": "User is not a member of this organization",
    "error.organization.permission_denied": "Permission denied. Admin access required",
    
    "error.internal_server": "Internal server error",
    "error.unexpected": "An unexpected error occurred: {error}",
    
    # Success Messages
    "success.operation.completed": "Operation completed successfully",
    "success.user.created": "User created successfully",
    "success.user.updated": "User updated successfully",
    "success.user.deleted": "User deleted successfully",
    
    "success.connector.connected": "{connector_type} connected successfully",
    "success.connector.disconnected": "{connector_type} disconnected successfully",
    "success.connector.sync_started": "Sync started successfully",
    
    "success.ingestion.completed": "Documents ingested successfully",
    "success.ingestion.partial": "Some documents ingested successfully ({count}/{total})",
    
    "success.knowledge_base.created": "Knowledge base created successfully",
    "success.knowledge_base.updated": "Knowledge base updated successfully",
    "success.knowledge_base.deleted": "Knowledge base deleted successfully",
    
    "success.organization.created": "Organization created successfully",
    "success.organization.member_added": "Member added to organization successfully",
    "success.organization.member_removed": "Member removed from organization successfully",
    
    "success.settings.updated": "Settings updated successfully",
    "success.vector_db.configured": "Vector database configured successfully",
    
    # Validation Messages
    "validation.required": "This field is required",
    "validation.email.invalid": "Invalid email address",
    "validation.password.too_short": "Password must be at least {min_length} characters",
    "validation.string.too_long": "String must not exceed {max_length} characters",
    "validation.number.too_small": "Number must be at least {min_value}",
    "validation.number.too_large": "Number must not exceed {max_value}",
    
    # Status Messages
    "status.sync.pending": "Sync is pending",
    "status.sync.queued": "Sync is queued",
    "status.sync.processing": "Sync in progress",
    "status.sync.completed": "Sync completed",
    "status.sync.failed": "Sync failed: {error}",
    
    "status.fine_tuning.pending": "Fine-tuning is pending",
    "status.fine_tuning.training": "Model is training",
    "status.fine_tuning.completed": "Fine-tuning completed",
    "status.fine_tuning.failed": "Fine-tuning failed: {error}",
    
    # Info Messages
    "info.no_results": "No results found",
    "info.loading": "Loading...",
    "info.processing": "Processing...",
    
    # Connector Messages
    "connector.slack": "Slack",
    "connector.teams": "Microsoft Teams",
    "connector.onedrive": "OneDrive",
    "connector.google_drive": "Google Drive",
    "connector.local_file": "Local Files",
    "connector.zendesk": "Zendesk",
    
    # Source Type Display Names
    "source_type.local_file": "Local Files",
    "source_type.google_drive": "Google Drive",
    "source_type.onedrive": "OneDrive",
    "source_type.slack": "Slack",
    "source_type.teams": "Microsoft Teams",
    "source_type.zendesk": "Zendesk",
    "source_type.web_scrape": "Web Search",
    
    # Share Type Display Names
    "share_type.public": "All Organization Members",
    "share_type.member": "Specific Members",
    "share_type.group": "Specific Groups",
    "share_type.private": "Private (Owner Only)",
    
    # Common Terms
    "common.save": "Save",
    "common.cancel": "Cancel",
    "common.delete": "Delete",
    "common.edit": "Edit",
    "common.create": "Create",
    "common.update": "Update",
    "common.search": "Search",
    "common.filter": "Filter",
    "common.loading": "Loading...",
    "common.error": "Error",
    "common.success": "Success",
    "common.warning": "Warning",
    "common.info": "Information",
}
