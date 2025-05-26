# Gerrit Provider: 负责与Gerrit API交互

from typing import Optional, Dict, Any
from urllib.parse import quote
from src.data.gerrit_api import make_gerrit_rest_request
from src.utils.logger import logger

class GerritProvider:
    def fetch_change(self, ctx, change_id: str, patchset_number: str = None) -> Dict[str, Any]:
        logger.info(f"[GerritProvider] fetch_change called with change_id={change_id}, patchset_number={patchset_number}")
        try:
            change_endpoint = f"a/changes/{change_id}/detail?o=CURRENT_REVISION&o=CURRENT_COMMIT&o=MESSAGES&o=DETAILED_LABELS&o=DETAILED_ACCOUNTS&o=ALL_REVISIONS&o=ALL_COMMITS&o=ALL_FILES&o=COMMIT_FOOTERS"
            change_info = make_gerrit_rest_request(ctx, change_endpoint)
            if not change_info:
                logger.warning(f"[GerritProvider] No change info found for change_id={change_id}")
                raise ValueError(f"Change {change_id} not found")
            project = change_info.get("project")
            if not project:
                logger.warning(f"[GerritProvider] No project info in change {change_id}")
                raise ValueError("Project information not found in change")
            current_revision = change_info.get("current_revision")
            revisions = change_info.get("revisions", {})
            if patchset_number:
                target_revision = None
                for rev, rev_info in revisions.items():
                    if str(rev_info.get("_number")) == str(patchset_number):
                        target_revision = rev
                        break
                if not target_revision:
                    available_patchsets = sorted([str(info.get("_number")) for info in revisions.values()])
                    logger.warning(f"[GerritProvider] Patchset {patchset_number} not found for change_id={change_id}. Available: {available_patchsets}")
                    raise ValueError(f"Patchset {patchset_number} not found. Available patchsets: {', '.join(available_patchsets)}")
            else:
                target_revision = current_revision
            if not target_revision or target_revision not in revisions:
                logger.warning(f"[GerritProvider] Revision info not found for change_id={change_id}, target_revision={target_revision}")
                raise ValueError("Revision information not found")
            revision_info = revisions[target_revision]
            processed_files = []
            for file_path, file_info in revision_info.get("files", {}).items():
                if file_path == "/COMMIT_MSG":
                    continue
                encoded_path = quote(file_path, safe='')
                diff_endpoint = f"a/changes/{change_id}/revisions/{target_revision}/files/{encoded_path}/diff"
                diff_info = make_gerrit_rest_request(ctx, diff_endpoint)
                file_data = {
                    "path": file_path,
                    "status": file_info.get("status", "MODIFIED"),
                    "lines_inserted": file_info.get("lines_inserted", 0),
                    "lines_deleted": file_info.get("lines_deleted", 0),
                    "size_delta": file_info.get("size_delta", 0),
                    "diff": diff_info
                }
                processed_files.append(file_data)
            logger.info(f"[GerritProvider] fetch_change succeeded for change_id={change_id}, patchset_number={patchset_number}, files_count={len(processed_files)}")
            return {
                "change_info": change_info,
                "project": project,
                "revision": target_revision,
                "patchset": revision_info,
                "files": processed_files
            }
        except Exception as e:
            logger.error(f"[GerritProvider] fetch_change failed: {str(e)}")
            raise

    def fetch_patchset_diff(self, ctx, change_id: str, base_patchset: str, target_patchset: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"[GerritProvider] fetch_patchset_diff called with change_id={change_id}, base_patchset={base_patchset}, target_patchset={target_patchset}, file_path={file_path}")
        try:
            change_endpoint = f"a/changes/{change_id}/detail?o=ALL_REVISIONS&o=ALL_FILES"
            change_info = make_gerrit_rest_request(ctx, change_endpoint)
            if not change_info:
                logger.warning(f"[GerritProvider] No change info found for change_id={change_id}")
                raise ValueError(f"Change {change_id} not found")
            revisions = change_info.get("revisions", {})
            base_revision = None
            target_revision = None
            for rev, rev_info in revisions.items():
                if str(rev_info.get("_number")) == str(base_patchset):
                    base_revision = rev
                if str(rev_info.get("_number")) == str(target_patchset):
                    target_revision = rev
            if not base_revision or not target_revision:
                available_patchsets = sorted([str(info.get("_number")) for info in revisions.values()])
                logger.warning(f"[GerritProvider] Patchset(s) not found for change_id={change_id}. Available: {available_patchsets}")
                raise ValueError(f"Patchset(s) not found. Available patchsets: {', '.join(available_patchsets)}")
            diff_endpoint = f"a/changes/{change_id}/revisions/{target_revision}/files"
            if base_revision:
                diff_endpoint += f"?base={base_revision}"
            files_diff = make_gerrit_rest_request(ctx, diff_endpoint)
            changed_files = {}
            for fpath, file_info in files_diff.items():
                if fpath == "/COMMIT_MSG":
                    continue
                if file_info.get("status") != "SAME":
                    encoded_path = quote(fpath, safe='')
                    file_diff_endpoint = f"a/changes/{change_id}/revisions/{target_revision}/files/{encoded_path}/diff"
                    if base_revision:
                        file_diff_endpoint += f"?base={base_revision}"
                    diff_info = make_gerrit_rest_request(ctx, file_diff_endpoint)
                    changed_files[fpath] = {
                        "status": file_info.get("status", "MODIFIED"),
                        "lines_inserted": file_info.get("lines_inserted", 0),
                        "lines_deleted": file_info.get("lines_deleted", 0),
                        "size_delta": file_info.get("size_delta", 0),
                        "diff": diff_info
                    }
            logger.info(f"[GerritProvider] fetch_patchset_diff succeeded for change_id={change_id}, base_patchset={base_patchset}, target_patchset={target_patchset}, changed_files_count={len(changed_files)}")
            return {
                "base_revision": base_revision,
                "target_revision": target_revision,
                "base_patchset": base_patchset,
                "target_patchset": target_patchset,
                "files": changed_files
            }
        except Exception as e:
            logger.error(f"[GerritProvider] fetch_patchset_diff failed: {str(e)}")
            raise 