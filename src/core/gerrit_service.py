# Gerrit Service Layer: 负责聚合Provider和业务逻辑

from typing import Optional, Dict, Any
from src.providers.gerrit_provider import GerritProvider
from src.utils.logger import logger

class GerritService:
    def __init__(self, provider: Optional[GerritProvider] = None):
        self.provider = provider or GerritProvider()

    def fetch_change(self, ctx, change_id: str, patchset_number: str = None) -> Dict[str, Any]:
        logger.info(f"[GerritService] fetch_change called with change_id={change_id}, patchset_number={patchset_number}")
        try:
            result = self.provider.fetch_change(ctx, change_id, patchset_number)
            logger.info(f"[GerritService] fetch_change succeeded for change_id={change_id}, patchset_number={patchset_number}")
            return result
        except Exception as e:
            logger.error(f"[GerritService] fetch_change failed: {str(e)}")
            raise

    def fetch_patchset_diff(self, ctx, change_id: str, base_patchset: str, target_patchset: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"[GerritService] fetch_patchset_diff called with change_id={change_id}, base_patchset={base_patchset}, target_patchset={target_patchset}, file_path={file_path}")
        try:
            result = self.provider.fetch_patchset_diff(ctx, change_id, base_patchset, target_patchset, file_path)
            logger.info(f"[GerritService] fetch_patchset_diff succeeded for change_id={change_id}, base_patchset={base_patchset}, target_patchset={target_patchset}, file_path={file_path}")
            return result
        except Exception as e:
            logger.error(f"[GerritService] fetch_patchset_diff failed: {str(e)}")
            raise 