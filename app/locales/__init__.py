"""Internationalization (i18n) support."""
from typing import Dict, Optional

# Default language
DEFAULT_LANGUAGE = "en"

# Supported languages
SUPPORTED_LANGUAGES = ["en"]  # Can be extended: ["en", "es", "fr", "de", "ja"]


def get_messages(language: str = DEFAULT_LANGUAGE) -> Dict[str, str]:
    """
    Get language messages for specified language.
    
    Args:
        language: Language code (default: 'en')
        
    Returns:
        Dictionary of message keys to translated strings
    """
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # Import language-specific messages
    if language == "en":
        from app.locales.en import messages
        return messages
    
    # Fallback to English
    from app.locales.en import messages
    return messages


def t(key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Translate a message key to the specified language.
    
    Args:
        key: Message key (e.g., 'error.not_found')
        language: Language code (default: 'en')
        **kwargs: Format parameters for message
        
    Returns:
        Translated message string
        
    Example:
        >>> t('error.not_found', resource='User')
        'User not found'
    """
    messages = get_messages(language)
    message = messages.get(key, key)  # Return key if not found
    
    # Format message with kwargs if provided
    if kwargs:
        try:
            return message.format(**kwargs)
        except KeyError:
            # If format fails, return message as-is
            return message
    
    return message
