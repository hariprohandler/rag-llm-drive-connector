"""SQL Agent service for Text-to-SQL query generation and execution."""
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
from langchain_core.language_models.chat_models import BaseChatModel
from typing import Optional, Dict, Any, List
from app.services.database_schema_service import get_database_engine
from app.services.llm_service import decrypt_api_key
from app.models import LLMConfig
from app.services.rag import get_llm_from_config


def _supports_tools(llm: BaseChatModel) -> bool:
    """
    Check if the LLM supports tool/function calling reliably.
    
    Note: Even if a model technically supports tools, we may use zero-shot
    for better reliability (e.g., GPT-4o-mini sometimes has parsing issues).
    
    Args:
        llm: LLM instance to check
    
    Returns:
        True if LLM supports tools reliably, False otherwise
    """
    # Check LLM type/class name to determine tool support
    llm_class_name = llm.__class__.__name__
    llm_str = str(llm).lower()
    
    # Check base_url to detect Ollama/custom models
    # ChatOpenAI instances have openai_api_base attribute
    base_url = getattr(llm, 'openai_api_base', None) or getattr(llm, 'base_url', None) or ""
    base_url_str = str(base_url).lower()
    
    # Check model name for specific models that have known issues
    # Try multiple ways to get model name
    model_name = (
        getattr(llm, 'model_name', None) or 
        getattr(llm, 'model', None) or 
        ""
    )
    model_name_str = str(model_name).lower()
    
    # Models that reliably support tools (exclude mini models that may have parsing issues)
    tools_supported_reliable = [
        "chatopenai",  # OpenAI models (but check model name)
        "chatanthropic",  # Anthropic Claude models
        "chatgooglegenerativeai",  # Google Gemini models (some versions)
    ]
    
    # Check if it's a custom/Ollama model (usually doesn't support tools)
    # Ollama typically uses localhost:11434 or has "ollama" in the URL
    is_custom_model = (
        "ollama" in base_url_str or 
        "localhost:11434" in base_url_str or 
        "127.0.0.1:11434" in base_url_str or
        (base_url and "openai.com" not in base_url_str and "api.anthropic.com" not in base_url_str and "generativelanguage.googleapis.com" not in base_url_str) or
        "ollama" in llm_str or 
        "custom" in llm_str.lower()
    )
    
    if is_custom_model:
        return False
    
    # Check class name
    for supported in tools_supported_reliable:
        if supported.lower() in llm_class_name.lower():
            # Double-check: if it's ChatOpenAI but has custom base_url, it's likely Ollama
            if "chatopenai" in llm_class_name.lower():
                if base_url and "openai.com" not in base_url_str:
                    return False
                # For OpenAI models, prefer zero-shot for mini models due to parsing issues
                # GPT-4o-mini and similar models sometimes have trouble with tool parsing
                if "mini" in model_name_str or "3.5" in model_name_str:
                    return False  # Use zero-shot for better reliability
                # GPT-4, GPT-4-turbo, GPT-4o (non-mini) work well with tools
                return True
            # Anthropic and Gemini models generally work well with tools
            return True
    
    # Default to False for unknown models (safer to use zero-shot)
    return False


def create_sql_agent_executor(
    connection_string: str,
    db_type: str,
    llm: BaseChatModel,
    schema_info: Optional[Dict[str, Any]] = None
):
    """
    Create a LangChain SQL agent for Text-to-SQL queries.
    
    Args:
        connection_string: Database connection string (encrypted)
        db_type: Database type ('postgresql', 'mysql', etc.)
        llm: LLM instance for SQL generation
        schema_info: Optional pre-inspected schema info for context
    
    Returns:
        SQL agent executor
    """
    # Decrypt connection string
    try:
        decrypted = decrypt_api_key(connection_string)
    except Exception:
        decrypted = connection_string
    
    # Normalize connection string for SQLDatabase
    if db_type == "postgresql":
        if not decrypted.startswith("postgresql://"):
            decrypted = decrypted.replace("postgresql+psycopg2://", "postgresql://")
            decrypted = decrypted.replace("postgres://", "postgresql://")
    elif db_type == "mysql":
        if not decrypted.startswith("mysql://"):
            decrypted = decrypted.replace("mysql+pymysql://", "mysql://")
    
    # Create SQLDatabase instance
    # LangChain's SQLDatabase handles connection pooling and query execution
    try:
        db = SQLDatabase.from_uri(decrypted)
    except Exception as e:
        raise Exception(f"Failed to connect to database: {str(e)}")
    
    # Create toolkit with database and LLM
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    
    # Determine agent type based on LLM capabilities
    # Check if LLM supports tools/function calling
    supports_tools = _supports_tools(llm)
    
    # Create SQL agent
    # This agent can:
    # 1. Inspect schema
    # 2. Generate SQL queries
    # 3. Execute queries safely
    # 4. Format results
    
    # Custom error handler for parsing errors
    def handle_parsing_error(error: Exception) -> str:
        """Handle parsing errors by returning a retry message."""
        error_str = str(error)
        if "Could not parse LLM output" in error_str:
            return "I need to generate a SQL query. Let me try again with a clearer approach."
        return "Let me reformulate my approach to generate the SQL query correctly."
    
    if supports_tools:
        # Use openai-tools for models that support function calling (better structured output)
        try:
            agent = create_sql_agent(
                llm=llm,
                toolkit=toolkit,
                verbose=True,
                agent_type="openai-tools",
                handle_parsing_errors=handle_parsing_error,  # Use custom handler function
                max_iterations=15,
                early_stopping_method="force"
            )
        except Exception as e:
            # If openai-tools fails, fall back to zero-shot
            print(f"Warning: openai-tools agent type failed, falling back to zero-shot: {e}")
            agent = create_sql_agent(
                llm=llm,
                toolkit=toolkit,
                verbose=True,
                agent_type="zero-shot-react-description",
                handle_parsing_errors=handle_parsing_error,  # Use custom handler function
                max_iterations=15,
                early_stopping_method="force"
            )
    else:
        # Use zero-shot-react-description for models that don't support tools (Ollama, etc.)
        agent = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            verbose=True,
            agent_type="zero-shot-react-description",
            handle_parsing_errors=handle_parsing_error,  # Use custom handler function
            max_iterations=15,
            early_stopping_method="force"
        )
    
    return agent


def _handle_parsing_error(error: Exception) -> str:
    """
    Custom handler for parsing errors in SQL agent.
    
    Args:
        error: The parsing error
    
    Returns:
        A message to retry the query
    """
    error_str = str(error)
    if "Could not parse LLM output" in error_str:
        return "I need to generate a SQL query. Let me try again with a clearer approach."
    return "Let me reformulate my approach to generate the SQL query correctly."


def execute_sql_query(
    query: str,
    connection_string: str,
    db_type: str,
    llm: BaseChatModel,
    schema_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute a natural language query against a database using SQL agent.
    
    Args:
        query: Natural language question (e.g., "How many tickets are open?")
        connection_string: Database connection string
        db_type: Database type
        llm: LLM for SQL generation
        schema_info: Optional schema info
    
    Returns:
        {
            "answer": "There are 150 open tickets.",
            "sql_query": "SELECT COUNT(*) FROM tickets WHERE status = 'open';",
            "result": [{"count": 150}],
            "sources": [{"type": "database", "table": "tickets"}]
        }
    """
    try:
        agent = create_sql_agent_executor(connection_string, db_type, llm, schema_info)
        
        # Execute query with retry logic for parsing errors
        max_retries = 2
        last_error = None
        
        result = None
        for attempt in range(max_retries):
            try:
                # Format query to be more explicit for SQL generation
                if attempt == 0:
                    formatted_query = query
                else:
                    # On retry, make the query more explicit
                    formatted_query = (
                        f"Question: {query}\n\n"
                        f"Please use the sql_db_query tool to execute a SQL query that answers this question. "
                        f"First, inspect the database schema, then generate and execute the appropriate SQL query."
                    )
                
                result = agent.invoke({"input": formatted_query})
                break
            except Exception as e:
                error_str = str(e)
                if "Could not parse LLM output" in error_str or "OUTPUT_PARSING_FAILURE" in error_str:
                    last_error = e
                    if attempt < max_retries - 1:
                        # Continue to next iteration with more explicit query
                        continue
                    else:
                        raise e
                else:
                    raise e
        
        if result is None:
            raise Exception("Failed to execute query after retries")
        
        # Extract SQL query from intermediate steps if available
        sql_query = ""
        if result.get("intermediate_steps"):
            for step in result.get("intermediate_steps", []):
                if isinstance(step, tuple) and len(step) >= 2:
                    tool_input = step[0]
                    if isinstance(tool_input, dict) and "query" in tool_input:
                        sql_query = tool_input["query"]
                        break
                    elif hasattr(tool_input, "tool_input") and isinstance(tool_input.tool_input, dict):
                        if "query" in tool_input.tool_input:
                            sql_query = tool_input.tool_input["query"]
                            break
                    # Also check for tool name and args
                    elif hasattr(tool_input, "tool") and hasattr(tool_input, "tool_input"):
                        tool_input_dict = tool_input.tool_input if isinstance(tool_input.tool_input, dict) else {}
                        if "query" in tool_input_dict:
                            sql_query = tool_input_dict["query"]
                            break
        
        # Extract result data
        result_data = []
        if result.get("intermediate_steps"):
            for step in result.get("intermediate_steps", []):
                if isinstance(step, tuple) and len(step) >= 2:
                    tool_output = step[1]
                    if isinstance(tool_output, (list, dict)):
                        result_data = tool_output if isinstance(tool_output, list) else [tool_output]
                        break
        
        return {
            "answer": result.get("output", ""),
            "sql_query": sql_query,
            "result": result_data,
            "sources": [{"type": "database", "connection": "external"}]
        }
    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages
        if "Could not parse LLM output" in error_msg or "OUTPUT_PARSING_FAILURE" in error_msg:
            error_msg = (
                "The LLM response could not be parsed. This may happen if the model doesn't follow "
                "the expected format. Try using a different LLM model (GPT-4, Claude) that better supports "
                "structured outputs, or rephrase your question."
            )
        return {
            "answer": f"Error executing SQL query: {error_msg}",
            "sql_query": "",
            "result": [],
            "sources": [],
            "error": error_msg
        }


def get_best_sql_model(llm_configs: List[LLMConfig], default_llm: BaseChatModel) -> BaseChatModel:
    """
    Select the best available model for SQL generation.
    
    Priority:
    1. GPT-4 / GPT-4 Turbo / GPT-4o
    2. Claude 3 Opus
    3. GPT-3.5 Turbo
    4. Claude 3 Sonnet
    5. Default provided model
    
    Args:
        llm_configs: List of available LLM configurations
        default_llm: Default LLM to use if no better option found
    
    Returns:
        Best available LLM for SQL generation
    """
    sql_models_priority = [
        ("openai", "gpt-4o"),
        ("openai", "gpt-4-turbo"),
        ("openai", "gpt-4"),
        ("anthropic", "claude-3-opus"),
        ("openai", "gpt-3.5-turbo"),
        ("anthropic", "claude-3-sonnet"),
    ]
    
    for provider, model_name in sql_models_priority:
        for config in llm_configs:
            if (config.provider.lower() == provider and 
                config.model_name and 
                model_name.lower() in config.model_name.lower()):
                try:
                    return get_llm_from_config(config)
                except Exception as e:
                    print(f"Error creating LLM from config {config.id}: {e}")
                    continue
    
    return default_llm


def is_sql_query(query: str) -> bool:
    """
    Detect if query requires SQL (count, aggregate, statistics).
    
    Args:
        query: Natural language query
    
    Returns:
        True if query likely requires SQL
    """
    sql_keywords = [
        "count", "how many", "total", "sum", "average", "avg", "max", "min",
        "group by", "aggregate", "statistics", "stats", "number of",
        "list all", "show me all", "what are all", "get all"
    ]
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in sql_keywords)

