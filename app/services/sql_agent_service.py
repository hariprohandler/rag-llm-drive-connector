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
    Check if the LLM supports tool/function calling.
    
    Args:
        llm: LLM instance to check
    
    Returns:
        True if LLM supports tools, False otherwise
    """
    # Check LLM type/class name to determine tool support
    llm_class_name = llm.__class__.__name__
    llm_str = str(llm).lower()
    
    # Check base_url to detect Ollama/custom models
    # ChatOpenAI instances have openai_api_base attribute
    base_url = getattr(llm, 'openai_api_base', None) or getattr(llm, 'base_url', None) or ""
    base_url_str = str(base_url).lower()
    
    # Models that support tools
    tools_supported = [
        "chatopenai",  # OpenAI models
        "chatanthropic",  # Anthropic Claude models
        "chatgooglegenerativeai",  # Google Gemini models (some versions)
    ]
    
    # Check if it's a custom/Ollama model (usually doesn't support tools)
    # Ollama typically uses localhost:11434 or has "ollama" in the URL
    # Also check if base_url is set (custom models usually have a custom base_url)
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
    for supported in tools_supported:
        if supported.lower() in llm_class_name.lower():
            # Double-check: if it's ChatOpenAI but has custom base_url, it's likely Ollama
            if "chatopenai" in llm_class_name.lower() and base_url and "openai.com" not in base_url_str:
                return False
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
    if supports_tools:
        # Use openai-tools for models that support function calling (better structured output)
        try:
            agent = create_sql_agent(
                llm=llm,
                toolkit=toolkit,
                verbose=True,
                agent_type="openai-tools",
                handle_parsing_errors=True,
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
                handle_parsing_errors=True,
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
            handle_parsing_errors=True,
            max_iterations=15,
            early_stopping_method="force"
        )
    
    return agent


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
        
        # Execute query
        result = agent.invoke({"input": query})
        
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
        return {
            "answer": f"Error executing SQL query: {str(e)}",
            "sql_query": "",
            "result": [],
            "sources": [],
            "error": str(e)
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

