"""Collection name prefix constants."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CollectionPrefix:
    """Collection name prefix constants."""
    
    USER_PREFIX = "user_"
    ORG_PREFIX = "org_"
    SOURCE_PREFIX = "source_"
    KB_PREFIX = "kb_"
    DOCUMENTS_SUFFIX = "_documents"
    
    @classmethod
    def user_collection(cls, user_id: str, suffix: str = None) -> str:
        """Generate user collection prefix."""
        if suffix:
            return f"{cls.USER_PREFIX}{user_id}_{suffix}"
        return f"{cls.USER_PREFIX}{user_id}{cls.DOCUMENTS_SUFFIX}"
    
    @classmethod
    def org_collection(cls, org_id: int, suffix: str = None) -> str:
        """Generate organization collection prefix."""
        if suffix:
            return f"{cls.ORG_PREFIX}{org_id}_{suffix}"
        return f"{cls.ORG_PREFIX}{org_id}{cls.DOCUMENTS_SUFFIX}"
