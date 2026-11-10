"""The API contract between the extension and the backend.

Keep in sync with docs/api-contract.md, extension/lib/types.ts and shared/*.json.
JSON uses camelCase (aiProbability); Python uses snake_case (ai_probability).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Seller(ApiModel):
    name: str | None = None
    cui: str | None = None


class LegalLinks(ApiModel):
    anpc: bool = False
    sol: bool = False


class PageData(ApiModel):
    """What the content script extracts from a product page."""

    url: str
    site: str | None = None
    title: str | None = None
    price: float | None = None
    currency: str | None = None
    images: list[str] = Field(default_factory=list)
    seller: Seller = Field(default_factory=Seller)
    legal_links: LegalLinks = Field(default_factory=LegalLinks)
    has_return_policy: bool = False


class ImageResult(ApiModel):
    url: str
    ai_probability: float = Field(ge=0, le=1)
    signals: list[str] = Field(default_factory=list)


class TrustCheck(ApiModel):
    id: str
    passed: bool
    message: str


class TrustReport(ApiModel):
    score: int = Field(ge=0, le=100)
    checks: list[TrustCheck]


class Citation(ApiModel):
    law: str
    article: str
    text: str
    link: str


class LegalReport(ApiModel):
    summary: str
    citations: list[Citation]


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class AnalysisResponse(ApiModel):
    analysis_id: str
    status: AnalysisStatus
    images: list[ImageResult] = Field(default_factory=list)
    trust: TrustReport | None = None
    legal: LegalReport | None = None
