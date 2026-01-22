"""Services for syncing data from various connectors (Gmail, Outlook, Teams, Slack)."""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials as GoogleCredentials
from googleapiclient.discovery import build
import requests
from langchain_core.documents import Document

from app.models import Connector, OAuthCredentials
from app.models.connector import ConnectorType, ConnectorStatus
from app.services.oauth_credential_service import get_google_credentials, get_microsoft_access_token
from app.constants import SourceType

logger = logging.getLogger(__name__)


def fetch_gmail_messages(
    credentials: GoogleCredentials,
    user_id: str,
    max_results: int = 100,
    after_date: Optional[datetime] = None,
    query: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetch messages from Gmail."""
    try:
        service = build('gmail', 'v1', credentials=credentials)
        
        # Build query
        search_query = []
        if after_date:
            # Gmail uses epoch seconds
            after_timestamp = int(after_date.timestamp())
            search_query.append(f"after:{after_timestamp}")
        if query:
            search_query.append(query)
        
        search_query_str = " ".join(search_query) if search_query else None
        
        # List messages
        results = service.users().messages().list(
            userId='me',
            maxResults=min(max_results, 500),
            q=search_query_str
        ).execute()
        
        messages = []
        message_ids = results.get('messages', [])
        
        # Fetch full message details
        for msg_item in message_ids[:max_results]:
            try:
                msg = service.users().messages().get(
                    userId='me',
                    id=msg_item['id'],
                    format='full'
                ).execute()
                
                # Extract headers
                headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
                
                # Extract body
                body = ""
                payload = msg.get('payload', {})
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part['mimeType'] == 'text/plain':
                            import base64
                            body = base64.urlsafe_b64decode(
                                part['body'].get('data', '')
                            ).decode('utf-8', errors='ignore')
                            break
                elif payload.get('mimeType') == 'text/plain':
                    import base64
                    body = base64.urlsafe_b64decode(
                        payload['body'].get('data', '')
                    ).decode('utf-8', errors='ignore')
                
                messages.append({
                    'id': msg['id'],
                    'thread_id': msg.get('threadId'),
                    'subject': headers.get('Subject', ''),
                    'from': headers.get('From', ''),
                    'to': headers.get('To', ''),
                    'date': headers.get('Date', ''),
                    'snippet': msg.get('snippet', ''),
                    'body': body,
                    'labels': msg.get('labelIds', []),
                    'internal_date': msg.get('internalDate')
                })
            except Exception as e:
                logger.error(f"Error fetching Gmail message {msg_item.get('id')}: {e}")
                continue
        
        return messages
    except Exception as e:
        logger.error(f"Error fetching Gmail messages: {e}")
        raise


def fetch_outlook_messages(
    access_token: str,
    user_id: str,
    max_results: int = 100,
    after_date: Optional[datetime] = None,
    folder_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetch messages from Outlook/Microsoft 365."""
    try:
        # Build URL
        if folder_id:
            url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}/messages"
        else:
            url = "https://graph.microsoft.com/v1.0/me/messages"
        
        # Add filters
        params = {
            '$top': min(max_results, 100),
            '$orderby': 'receivedDateTime desc',
            '$select': 'id,subject,from,toRecipients,body,receivedDateTime,isRead,conversationId'
        }
        
        if after_date:
            params['$filter'] = f"receivedDateTime ge {after_date.isoformat()}"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        messages = []
        while len(messages) < max_results:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            items = data.get('value', [])
            
            for item in items:
                messages.append({
                    'id': item.get('id'),
                    'conversation_id': item.get('conversationId'),
                    'subject': item.get('subject', ''),
                    'from': item.get('from', {}).get('emailAddress', {}).get('address', ''),
                    'to': [r.get('emailAddress', {}).get('address', '') for r in item.get('toRecipients', [])],
                    'received_date': item.get('receivedDateTime'),
                    'body': item.get('body', {}).get('content', ''),
                    'is_read': item.get('isRead', False)
                })
            
            # Check for next page
            next_link = data.get('@odata.nextLink')
            if not next_link or len(messages) >= max_results:
                break
            
            url = next_link
            params = {}  # URL already contains params
        
        return messages[:max_results]
    except Exception as e:
        logger.error(f"Error fetching Outlook messages: {e}")
        raise


def fetch_slack_messages(
    access_token: str,
    user_id: str,
    channel_ids: Optional[List[str]] = None,
    max_results: int = 100,
    after_timestamp: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Fetch messages from Slack."""
    try:
        if not channel_ids:
            # Get list of channels
            channels_url = "https://slack.com/api/conversations.list"
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(channels_url, headers=headers, params={'types': 'public_channel,private_channel'})
            response.raise_for_status()
            channels_data = response.json()
            if not channels_data.get('ok'):
                raise Exception(f"Slack API error: {channels_data.get('error')}")
            channel_ids = [ch['id'] for ch in channels_data.get('channels', [])]
        
        messages = []
        for channel_id in channel_ids[:10]:  # Limit to 10 channels
            try:
                url = f"https://slack.com/api/conversations.history"
                params = {
                    'channel': channel_id,
                    'limit': min(max_results, 200)
                }
                if after_timestamp:
                    params['oldest'] = str(after_timestamp)
                
                headers = {'Authorization': f'Bearer {access_token}'}
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                if not data.get('ok'):
                    logger.warning(f"Slack API error for channel {channel_id}: {data.get('error')}")
                    continue
                
                for msg in data.get('messages', []):
                    messages.append({
                        'id': msg.get('ts'),
                        'channel_id': channel_id,
                        'user': msg.get('user', ''),
                        'text': msg.get('text', ''),
                        'timestamp': msg.get('ts'),
                        'thread_ts': msg.get('thread_ts'),
                        'type': msg.get('type', 'message')
                    })
            except Exception as e:
                logger.error(f"Error fetching Slack messages from channel {channel_id}: {e}")
                continue
        
        return messages[:max_results]
    except Exception as e:
        logger.error(f"Error fetching Slack messages: {e}")
        raise


def fetch_teams_messages(
    access_token: str,
    user_id: str,
    chat_ids: Optional[List[str]] = None,
    max_results: int = 100,
    after_date: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Fetch messages from Microsoft Teams."""
    try:
        messages = []
        
        # Get chats
        if not chat_ids:
            url = "https://graph.microsoft.com/v1.0/me/chats"
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            chats_data = response.json()
            chat_ids = [chat['id'] for chat in chats_data.get('value', [])]
        
        for chat_id in chat_ids[:10]:  # Limit to 10 chats
            try:
                url = f"https://graph.microsoft.com/v1.0/me/chats/{chat_id}/messages"
                params = {'$top': min(max_results, 50)}
                
                if after_date:
                    params['$filter'] = f"lastModifiedDateTime ge {after_date.isoformat()}"
                
                headers = {'Authorization': f'Bearer {access_token}'}
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                for item in data.get('value', []):
                    messages.append({
                        'id': item.get('id'),
                        'chat_id': chat_id,
                        'from': item.get('from', {}).get('user', {}).get('displayName', ''),
                        'body': item.get('body', {}).get('content', ''),
                        'created_date': item.get('createdDateTime'),
                        'message_type': item.get('messageType', 'message')
                    })
            except Exception as e:
                logger.error(f"Error fetching Teams messages from chat {chat_id}: {e}")
                continue
        
        return messages[:max_results]
    except Exception as e:
        logger.error(f"Error fetching Teams messages: {e}")
        raise


def convert_messages_to_documents(
    messages: List[Dict[str, Any]],
    source_type: str,
    connector_id: Optional[int] = None,
    user_id: Optional[str] = None,
    knowledge_base_id: Optional[int] = None
) -> List[Document]:
    """Convert messages to LangChain Document objects."""
    documents = []
    
    for msg in messages:
        # Build content
        if source_type == SourceType.GMAIL.value:
            content = f"Subject: {msg.get('subject', 'No Subject')}\n"
            content += f"From: {msg.get('from', '')}\n"
            content += f"To: {msg.get('to', '')}\n"
            content += f"Date: {msg.get('date', '')}\n"
            content += f"\n{msg.get('body', msg.get('snippet', ''))}"
            
            metadata = {
                'source': 'gmail',
                'source_type': SourceType.GMAIL.value,
                'message_id': msg.get('id'),
                'thread_id': msg.get('thread_id'),
                'subject': msg.get('subject', ''),
                'from': msg.get('from', ''),
                'to': msg.get('to', ''),
                'date': msg.get('date', ''),
                'labels': ','.join(msg.get('labels', []))
            }
        elif source_type == SourceType.OUTLOOK.value:
            content = f"Subject: {msg.get('subject', 'No Subject')}\n"
            content += f"From: {msg.get('from', '')}\n"
            content += f"To: {', '.join(msg.get('to', []))}\n"
            content += f"Date: {msg.get('received_date', '')}\n"
            content += f"\n{msg.get('body', '')}"
            
            metadata = {
                'source': 'outlook',
                'source_type': SourceType.OUTLOOK.value,
                'message_id': msg.get('id'),
                'conversation_id': msg.get('conversation_id'),
                'subject': msg.get('subject', ''),
                'from': msg.get('from', ''),
                'to': ','.join(msg.get('to', [])),
                'received_date': msg.get('received_date', ''),
                'is_read': msg.get('is_read', False)
            }
        elif source_type == SourceType.SLACK.value:
            content = f"Channel: {msg.get('channel_id', '')}\n"
            content += f"User: {msg.get('user', '')}\n"
            content += f"Timestamp: {msg.get('timestamp', '')}\n"
            content += f"\n{msg.get('text', '')}"
            
            metadata = {
                'source': 'slack',
                'source_type': SourceType.SLACK.value,
                'message_id': msg.get('id'),
                'channel_id': msg.get('channel_id', ''),
                'user': msg.get('user', ''),
                'timestamp': msg.get('timestamp', ''),
                'thread_ts': msg.get('thread_ts'),
                'type': msg.get('type', 'message')
            }
        elif source_type == SourceType.TEAMS.value:
            content = f"Chat: {msg.get('chat_id', '')}\n"
            content += f"From: {msg.get('from', '')}\n"
            content += f"Date: {msg.get('created_date', '')}\n"
            content += f"\n{msg.get('body', '')}"
            
            metadata = {
                'source': 'teams',
                'source_type': SourceType.TEAMS.value,
                'message_id': msg.get('id'),
                'chat_id': msg.get('chat_id', ''),
                'from': msg.get('from', ''),
                'created_date': msg.get('created_date', ''),
                'message_type': msg.get('message_type', 'message')
            }
        else:
            continue
        
        # Add common metadata
        if connector_id:
            metadata['connector_id'] = connector_id
        if user_id:
            metadata['user_id'] = user_id
        if knowledge_base_id:
            metadata['knowledge_base_id'] = knowledge_base_id
        
        documents.append(Document(page_content=content, metadata=metadata))
    
    return documents
