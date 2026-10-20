"""
HDFS File Management Service.
Business logic layer coordinating directory browsing, uploads, downloads,
safe staging, and mutating filesystem operations with strict guardrails.
"""

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
from werkzeug.utils import secure_filename

from ..config import Config
from .hadoop_adapter import (
    HadoopAdapter,
    HadoopError,
    HadoopExecutionError,
    HadoopItemExistsError,
    HadoopNotFoundError,
    HadoopPathError,
    ProtectedPathError,
)

logger = logging.getLogger(__name__)


class HdfsServiceError(HadoopError):
    """Base exception for HdfsService errors."""
    pass


class HdfsService:
    """High-level service for HDFS file explorer and manipulation."""

    # Disallow invalid or dangerous folder/file names
    ILLEGAL_NAME_PATTERN = re.compile(r'[/\\:\*\?"<>\|\x00-\x1f\x7f\s;`$&~]')

    def __init__(self, adapter: Optional[HadoopAdapter] = None, config: Optional[Config] = None):
        self.config = config or Config()
        self.adapter = adapter or HadoopAdapter(self.config)

    @classmethod
    def sanitize_item_name(cls, name: str) -> str:
        """
        Validates and sanitizes a single directory or file name component.
        Prohibits slashes, traversal sequences, whitespace, and special characters.
        """
        if not name or not isinstance(name, str):
            raise HadoopPathError("Item name cannot be empty.")

        name = name.strip()

        if name in (".", ".."):
            raise HadoopPathError("Item name cannot be '.' or '..'.")

        if "/" in name or "\\" in name:
            raise HadoopPathError(f"Item name cannot contain path separators ('/', '\\'): '{name}'")

        if cls.ILLEGAL_NAME_PATTERN.search(name):
            raise HadoopPathError(
                f"Item name contains invalid characters or whitespace: '{name}'. "
                "Use alphanumeric characters, underscores, hyphens, and dots only."
            )

        return name

    def build_breadcrumbs(self, path: str) -> List[Dict[str, Any]]:
        """
        Builds a hierarchical list of breadcrumbs for UI navigation.
        Example: '/user/chethan' -> [
            {'name': 'Root', 'path': '/'},
            {'name': 'user', 'path': '/user'},
            {'name': 'chethan', 'path': '/user/chethan', 'active': True}
        ]
        """
        sanitized = self.adapter.sanitize_hdfs_path(path)
        parts = [p for p in sanitized.split("/") if p]

        breadcrumbs = [{"name": "Root (/)", "path": "/"}]
        current_path = ""

        for part in parts:
            current_path += "/" + part
            breadcrumbs.append({
                "name": part,
                "path": current_path,
                "active": False
            })

        if breadcrumbs:
            breadcrumbs[-1]["active"] = True

        return breadcrumbs

    def get_parent_path(self, path: str) -> str:
        """Returns the parent directory path, bounded at root '/'."""
        sanitized = self.adapter.sanitize_hdfs_path(path)
        if sanitized == "/":
            return "/"
        parent = os.path.dirname(sanitized)
        return parent or "/"

    def browse_directory(self, path: str = "/user/chethan") -> Dict[str, Any]:
        """
        Fetches directory contents, builds navigation breadcrumbs, and tags
        protected items so the UI can disable destructive action buttons.
        """
        sanitized = self.adapter.sanitize_hdfs_path(path)
        listing = self.adapter.list_hdfs_directory(sanitized)

        protected_paths = getattr(self.config, "PROTECTED_HDFS_PATHS", set())

        # Annotate each entry with protection flag
        annotated_entries = []
        for entry in listing.get("entries", []):
            item_path = entry.get("path", "")
            is_protected = item_path in protected_paths
            # Also check if entry is an ancestor of a protected path
            has_protected_children = any(p.startswith(item_path.rstrip("/") + "/") for p in protected_paths)

            annotated_entries.append({
                **entry,
                "is_protected": is_protected or has_protected_children
            })

        is_current_protected = (
            sanitized in protected_paths or
            any(p.startswith(sanitized.rstrip("/") + "/") for p in protected_paths)
        )

        return {
            "status": listing.get("status", "Online"),
            "current_path": sanitized,
            "parent_path": self.get_parent_path(sanitized),
            "breadcrumbs": self.build_breadcrumbs(sanitized),
            "entries": annotated_entries,
            "total_count": len(annotated_entries),
            "source": listing.get("source", "WebHDFS"),
            "is_protected": is_current_protected,
            "error": listing.get("error")
        }

    def create_directory(self, parent_dir: str, folder_name: str) -> Dict[str, Any]:
        """Validates folder name and parent directory, then creates folder in HDFS."""
        sanitized_parent = self.adapter.sanitize_hdfs_path(parent_dir)
        sanitized_name = self.sanitize_item_name(folder_name)

        target_path = f"{sanitized_parent.rstrip('/')}/{sanitized_name}"
        return self.adapter.mkdir(target_path)

    def handle_upload(
        self,
        file_storage,
        target_dir: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Saves an uploaded file to the local staging directory, validates its
        size and name, and transfers it to HDFS via zero-copy WSL mount path.
        Guarantees local staging file cleanup in all scenarios.
        """
        if not file_storage or not getattr(file_storage, "filename", None):
            raise HadoopPathError("No file was selected for upload.")

        raw_filename = secure_filename(file_storage.filename)
        safe_filename = self.sanitize_item_name(raw_filename or "uploaded_file")
        sanitized_target_dir = self.adapter.sanitize_hdfs_path(target_dir)

        target_hdfs_path = f"{sanitized_target_dir.rstrip('/')}/{safe_filename}"

        # Immediately guard against protected system paths before creating any temp files
        self.adapter.check_protected_path(
            target_hdfs_path,
            operation="overwrite" if overwrite else "upload to"
        )

        # Ensure local staging directory exists
        staging_dir = Path(getattr(self.config, "TEMP_STAGING_DIR", Path.cwd() / ".temp_staging"))
        staging_dir.mkdir(parents=True, exist_ok=True)

        unique_prefix = uuid.uuid4().hex[:12]
        staged_local_file = staging_dir / f"{unique_prefix}_{safe_filename}"

        try:
            # Save upload stream to temporary staging on Windows host (supports FileStorage & BytesIO)
            if hasattr(file_storage, "save"):
                file_storage.save(str(staged_local_file))
            elif hasattr(file_storage, "read"):
                if hasattr(file_storage, "seek"):
                    file_storage.seek(0)
                with open(staged_local_file, "wb") as f:
                    f.write(file_storage.read())
            else:
                raise HadoopExecutionError("Unsupported file object provided for upload.")

            file_size = os.path.getsize(str(staged_local_file))

            max_size = getattr(self.config, "MAX_UPLOAD_SIZE_BYTES", 100 * 1024 * 1024)
            if file_size > max_size:
                raise HadoopExecutionError(
                    f"File exceeds maximum upload size of {max_size / (1024 * 1024):.0f} MB."
                )

            # Delegate to adapter put_file
            result = self.adapter.put_file(
                local_win_path=str(staged_local_file),
                hdfs_target_path=target_hdfs_path,
                overwrite=overwrite
            )
            result["filename"] = safe_filename
            result["bytes"] = file_size
            return result

        finally:
            # Clean up local staging file immediately
            if staged_local_file.exists():
                try:
                    os.remove(str(staged_local_file))
                except Exception as cleanup_err:
                    logger.warning("Failed to remove staging file %s: %s", staged_local_file, cleanup_err)

    def copy_item(
        self,
        source_path: str,
        dest_dir: str,
        new_name: Optional[str] = None,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """Copies an item to destination directory with optional renaming."""
        sanitized_src = self.adapter.sanitize_hdfs_path(source_path)
        sanitized_dest_dir = self.adapter.sanitize_hdfs_path(dest_dir)

        final_name = self.sanitize_item_name(new_name) if new_name else os.path.basename(sanitized_src)
        target_dest = f"{sanitized_dest_dir.rstrip('/')}/{final_name}"

        return self.adapter.copy_item(sanitized_src, target_dest, overwrite=overwrite)

    def rename_item(self, source_path: str, new_name: str) -> Dict[str, Any]:
        """Renames an item within its existing directory."""
        sanitized_src = self.adapter.sanitize_hdfs_path(source_path)
        sanitized_new_name = self.sanitize_item_name(new_name)

        parent_dir = os.path.dirname(sanitized_src) or "/"
        target_dest = f"{parent_dir.rstrip('/')}/{sanitized_new_name}"

        return self.adapter.rename_item(sanitized_src, target_dest)

    def delete_item(
        self,
        hdfs_path: str,
        recursive: bool = False,
        confirmation_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Deletes an item from HDFS with strict protection checks."""
        sanitized = self.adapter.sanitize_hdfs_path(hdfs_path)
        return self.adapter.delete_item(
            sanitized,
            recursive=recursive,
            confirmation_name=confirmation_name
        )

    def get_download_stream(self, hdfs_path: str) -> Tuple[Generator[bytes, None, None], str]:
        """
        Prepares a streaming binary response for file download.
        Returns a tuple of (byte_generator, filename).
        """
        sanitized = self.adapter.sanitize_hdfs_path(hdfs_path)
        filename = os.path.basename(sanitized) or "downloaded_file"
        stream = self.adapter.stream_file_content(sanitized)
        return stream, filename
