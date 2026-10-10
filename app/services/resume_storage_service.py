"""
Resume Storage Service for RecruitFlow AI (Phase 4).
Handles secure file validation, magic-byte inspection, UUID storage key generation,
safe disk persistence outside the web root, and path-traversal-free file access.
"""
import os
import uuid
import zipfile
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app

# Maximum file size: 5 MB
MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf", ".docx"}

# Magic byte signatures
PDF_MAGIC_HEADER = b"%PDF-"
ZIP_MAGIC_HEADER = b"PK\x03\x04"


class ResumeStorageError(Exception):
    """Custom exception for resume storage and validation failures."""
    def __init__(self, message, error_code="storage_error"):
        super().__init__(message)
        self.error_code = error_code


class ResumeStorageService:
    """Manages secure upload validation, disk storage, and retrieval for resume documents."""

    @staticmethod
    def get_storage_dir() -> Path:
        """Returns the absolute Path to the resume storage directory, creating it if needed."""
        base_upload = current_app.config.get("UPLOAD_FOLDER")
        if not base_upload:
            base_upload = Path(current_app.root_path).parent / "uploads"
        else:
            base_upload = Path(base_upload)
            
        resumes_dir = base_upload / "resumes"
        resumes_dir.mkdir(parents=True, exist_ok=True)
        return resumes_dir

    @classmethod
    def validate_file(cls, file_storage) -> dict:
        """
        Validates the incoming file before saving:
        1. Checks filename existence and allowed extensions (.pdf, .docx).
        2. Checks file size against 5MB limit.
        3. Inspects magic bytes / file signature to prevent renamed malicious files.

        Returns dict with:
        - original_filename
        - extension (.pdf or .docx)
        - mime_type
        - file_size_bytes
        - content_bytes
        """
        if not file_storage or not file_storage.filename:
            raise ResumeStorageError("No file was uploaded or filename is empty.", "empty_file")

        raw_name = file_storage.filename
        safe_name = secure_filename(raw_name)
        if not safe_name:
            safe_name = "resume"

        # Determine extension
        _, ext = os.path.splitext(raw_name)
        ext = ext.lower()

        if ext not in ALLOWED_EXTENSIONS:
            allowed_str = ", ".join(ALLOWED_EXTENSIONS)
            raise ResumeStorageError(
                f"Unsupported file format '{ext}'. Only {allowed_str} files are accepted.",
                "invalid_extension"
            )

        # Read contents to check size and magic bytes
        file_storage.seek(0, os.SEEK_END)
        size_bytes = file_storage.tell()
        file_storage.seek(0)

        if size_bytes == 0:
            raise ResumeStorageError("The uploaded file is empty (0 bytes).", "empty_content")

        if size_bytes > MAX_RESUME_SIZE_BYTES:
            max_mb = MAX_RESUME_SIZE_BYTES / (1024 * 1024)
            raise ResumeStorageError(
                f"File size ({size_bytes / (1024 * 1024):.2f} MB) exceeds maximum permitted limit of {max_mb:.0f} MB.",
                "file_too_large"
            )

        content_bytes = file_storage.read()
        file_storage.seek(0)

        # Magic byte inspection
        if ext == ".pdf":
            if not content_bytes.startswith(PDF_MAGIC_HEADER):
                raise ResumeStorageError(
                    "File header does not match a valid PDF document (%PDF- signature missing).",
                    "invalid_pdf_signature"
                )
            mime_type = "application/pdf"

        elif ext == ".docx":
            if not content_bytes.startswith(ZIP_MAGIC_HEADER):
                raise ResumeStorageError(
                    "File header does not match a valid DOCX document (ZIP signature missing).",
                    "invalid_docx_signature"
                )
            # Verify it is a valid zip archive containing word XML structure
            import io
            try:
                with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
                    namelist = zf.namelist()
                    if not any("word/" in name or "[Content_Types].xml" in name for name in namelist):
                        raise ResumeStorageError(
                            "The file is a valid ZIP archive but does not contain standard DOCX components.",
                            "corrupted_docx"
                        )
            except zipfile.BadZipFile:
                raise ResumeStorageError("The DOCX file is corrupted or not a valid archive.", "corrupted_docx")

            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        else:
            mime_type = "application/octet-stream"

        return {
            "original_filename": raw_name,
            "sanitized_filename": safe_name,
            "extension": ext,
            "mime_type": mime_type,
            "file_size_bytes": size_bytes,
            "content_bytes": content_bytes,
        }

    @classmethod
    def save_file(cls, file_storage) -> dict:
        """
        Validates and stores the file with a unique UUID key on disk.
        Returns metadata dictionary for database persistence.
        """
        meta = cls.validate_file(file_storage)
        storage_dir = cls.get_storage_dir()

        storage_key = uuid.uuid4().hex
        stored_filename = f"{storage_key}{meta['extension']}"
        target_path = storage_dir / stored_filename

        # Write safely to disk
        with open(target_path, "wb") as f:
            f.write(meta["content_bytes"])

        return {
            "storage_key": storage_key,
            "filename": stored_filename,
            "original_filename": meta["original_filename"],
            "file_path": str(target_path),
            "file_type": meta["extension"].lstrip("."),
            "file_extension": meta["extension"],
            "file_size": meta["file_size_bytes"],
            "file_size_bytes": meta["file_size_bytes"],
            "mime_type": meta["mime_type"],
        }

    @classmethod
    def get_absolute_path(cls, stored_filename_or_key: str) -> Path:
        """
        Safely resolves stored file path, preventing directory traversal attacks.
        Raises ResumeStorageError if path traversal is detected or file does not exist.
        """
        storage_dir = cls.get_storage_dir().resolve()
        
        # Clean parameter
        clean_target = os.path.basename(stored_filename_or_key)
        candidate = (storage_dir / clean_target).resolve()

        # Prevent traversal
        if not candidate.is_relative_to(storage_dir):
            raise ResumeStorageError("Illegal file path access attempt.", "path_traversal")

        if not candidate.exists():
            # If not found directly, try with extension match by storage key prefix
            matches = list(storage_dir.glob(f"{clean_target}.*"))
            if matches and matches[0].exists():
                return matches[0]
            raise ResumeStorageError(f"Resume file not found on disk: {clean_target}", "file_not_found")

        return candidate

    @classmethod
    def delete_file(cls, stored_filename: str) -> bool:
        """Removes the stored file from disk if present."""
        try:
            path = cls.get_absolute_path(stored_filename)
            if path.exists():
                import gc
                gc.collect()
                try:
                    path.unlink()
                    return True
                except OSError:
                    # Windows file handle might still be closing in asynchronous WSGI server
                    return False
        except (ResumeStorageError, OSError):
            pass
        return False

