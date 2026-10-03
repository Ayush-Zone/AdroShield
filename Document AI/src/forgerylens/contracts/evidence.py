from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class EvidenceStatus(str, Enum):
    OK = "ok"
    AMBIGUOUS = "ambiguous"
    NOT_ANALYZABLE = "not_analyzable"

class Provenance(BaseModel):
    source_file_sha256: str = Field(..., description="SHA-256 hash of the source file")
    tool_name: str = Field(..., description="Name of the tool that generated the evidence")
    tool_version: str = Field(..., description="Version of the tool")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters used during generation")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the evidence was generated")

class EvidenceLocation(BaseModel):
    page_number: int = Field(..., ge=1)
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., ge=0.0, le=1.0)
    height: float = Field(..., ge=0.0, le=1.0)

class EvidenceRecord(BaseModel):
    id: str = Field(..., description="Unique identifier for this evidence record")
    type: str = Field(..., description="Type of evidence (e.g., 'text_extraction', 'metadata_anomaly')")
    observation: Any = Field(..., description="What was actually observed (raw data, string, etc.)")
    location: Optional[EvidenceLocation] = Field(default=None, description="Where the observation was found")
    method: str = Field(..., description="Methodology used to make the observation")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence score")
    calibrated_confidence: bool = Field(default=False, description="Flag indicating if the confidence is calibrated")
    status: EvidenceStatus = Field(..., description="Status of the observation")
    limitations: str = Field(default="", description="Known limitations or caveats for this observation")
    raw_ref: Optional[str] = Field(default=None, description="Pointer/URI to the stored raw artifact")
    provenance: Provenance = Field(..., description="Provenance information")
