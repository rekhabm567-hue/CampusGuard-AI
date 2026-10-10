from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DocumentMetadata:
    title: str
    department: str
    document_type: str
    academic_year: Optional[int] = None
    version: str = "1.0"
    effective_date: Optional[str] = None
    allowed_roles: List[str] = field(default_factory=list)
    file_path: Optional[str] = None
    # New documents are drafts until someone approves them.
    status: str = "draft"
    expiration_date: Optional[str] = None
    superseded_by: Optional[str] = None
    owner: Optional[str] = None

    def to_dict(self):
        return {
            "title": self.title,
            "department": self.department,
            "document_type": self.document_type,
            "academic_year": self.academic_year,
            "version": self.version,
            "effective_date": self.effective_date,
            "allowed_roles": self.allowed_roles,
            "file_path": self.file_path,
            "status": self.status,
            "expiration_date": self.expiration_date,
            "superseded_by": self.superseded_by,
            "owner": self.owner,
        }


def create_metadata(
    title,
    department,
    document_type,
    academic_year=None,
    version="1.0",
    effective_date=None,
    allowed_roles=None,
    file_path=None,
    status="draft",
    expiration_date=None,
    superseded_by=None,
    owner=None,
):
    if allowed_roles is None:
        allowed_roles = []

    return DocumentMetadata(
        title=title,
        department=department,
        document_type=document_type,
        academic_year=academic_year,
        version=version,
        effective_date=effective_date,
        allowed_roles=allowed_roles,
        file_path=file_path,
        status=status,
        expiration_date=expiration_date,
        superseded_by=superseded_by,
        owner=owner,
    )