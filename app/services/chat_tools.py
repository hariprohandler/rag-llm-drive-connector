"""Tools/functions available to the LLM in chat conversations."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from langchain_core.tools import Tool
from langchain_core.callbacks import CallbackManagerForToolRun

from app.models import Connector
from app.models.connector import ConnectorType, ConnectorStatus
from app.services.sync_worker import create_connector_sync_job


def get_connector_tools(db: Session, user_id: str) -> List[Tool]:
    """
    Get LangChain tools for available connectors.
    These tools can be used by the LLM in chat conversations.
    """
    tools = []
    
    # Get all connected connectors for the user
    connectors = db.query(Connector).filter(
        Connector.user_id == user_id,
        Connector.status == ConnectorStatus.CONNECTED,
        Connector.is_active == True
    ).all()
    
    for connector in connectors:
        if connector.connector_type == ConnectorType.GMAIL:
            tools.append(Tool(
                name="sync_gmail",
                description="Sync emails from Gmail. Use this to fetch and index new emails from the user's Gmail account.",
                func=lambda query: sync_gmail_tool(db, user_id, connector.id, query)
            ))
        elif connector.connector_type == ConnectorType.OUTLOOK:
            tools.append(Tool(
                name="sync_outlook",
                description="Sync emails from Outlook. Use this to fetch and index new emails from the user's Outlook account.",
                func=lambda query: sync_outlook_tool(db, user_id, connector.id, query)
            ))
        elif connector.connector_type == ConnectorType.SLACK:
            tools.append(Tool(
                name="sync_slack",
                description="Sync messages from Slack. Use this to fetch and index new messages from the user's Slack workspace.",
                func=lambda query: sync_slack_tool(db, user_id, connector.id, query)
            ))
        elif connector.connector_type == ConnectorType.TEAMS:
            tools.append(Tool(
                name="sync_teams",
                description="Sync messages from Microsoft Teams. Use this to fetch and index new messages from the user's Teams chats.",
                func=lambda query: sync_teams_tool(db, user_id, connector.id, query)
            ))
    
    return tools


def sync_gmail_tool(db: Session, user_id: str, connector_id: int, query: str = "") -> str:
    """Tool function to sync Gmail."""
    try:
        sync_job = create_connector_sync_job(
            db=db,
            connector_id=connector_id,
            user_id=user_id,
            organization_id=None,
            knowledge_base_id=None,
            sync_scope={"max_results": 50, "query": query} if query else {"max_results": 50},
            priority=5
        )
        return f"Gmail sync job queued (ID: {sync_job.id}). The sync will resume from the last sync point and fetch new emails."
    except Exception as e:
        return f"Error syncing Gmail: {str(e)}"


def sync_outlook_tool(db: Session, user_id: str, connector_id: int, query: str = "") -> str:
    """Tool function to sync Outlook."""
    try:
        sync_job = create_connector_sync_job(
            db=db,
            connector_id=connector_id,
            user_id=user_id,
            organization_id=None,
            knowledge_base_id=None,
            sync_scope={"max_results": 50},
            priority=5
        )
        return f"Outlook sync job queued (ID: {sync_job.id}). The sync will resume from the last sync point and fetch new emails."
    except Exception as e:
        return f"Error syncing Outlook: {str(e)}"


def sync_slack_tool(db: Session, user_id: str, connector_id: int, query: str = "") -> str:
    """Tool function to sync Slack."""
    try:
        sync_job = create_connector_sync_job(
            db=db,
            connector_id=connector_id,
            user_id=user_id,
            organization_id=None,
            knowledge_base_id=None,
            sync_scope={"max_results": 100},
            priority=5
        )
        return f"Slack sync job queued (ID: {sync_job.id}). The sync will resume from the last sync point and fetch new messages."
    except Exception as e:
        return f"Error syncing Slack: {str(e)}"


def sync_teams_tool(db: Session, user_id: str, connector_id: int, query: str = "") -> str:
    """Tool function to sync Teams."""
    try:
        sync_job = create_connector_sync_job(
            db=db,
            connector_id=connector_id,
            user_id=user_id,
            organization_id=None,
            knowledge_base_id=None,
            sync_scope={"max_results": 100},
            priority=5
        )
        return f"Teams sync job queued (ID: {sync_job.id}). The sync will resume from the last sync point and fetch new messages."
    except Exception as e:
        return f"Error syncing Teams: {str(e)}"
