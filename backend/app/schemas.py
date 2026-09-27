from pydantic import BaseModel, Field


class RenderRequest(BaseModel):
    puml: str = Field(..., min_length=1, description="PlantUML source code")
    format: str = Field(default="svg", pattern="^(svg|png)$")


class D2RenderRequest(BaseModel):
    code: str = Field(..., min_length=1, description="D2 source code")
    format: str = Field(default="svg", pattern="^(svg|png)$")


class RenderResponse(BaseModel):
    image: str = Field(..., description="Base64 data URI of the rendered diagram")
    format: str


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


class GenerateV2Response(BaseModel):
    renderer: str = Field(..., description="Renderer: plantuml, d2, or excalidraw")
    category: str = Field(..., description="Diagram category detected")
    code: str | None = Field(default=None, description="Diagram source code (PlantUML or D2) — null for excalidraw")
    image: str | None = Field(default=None, description="Base64 data URI of rendered image — null for excalidraw")
    excalidraw_data: dict | None = Field(default=None, description="Excalidraw scene JSON — null for graph track")
    prompt_used: str


class ErrorResponse(BaseModel):
    detail: str


class HistoryItem(BaseModel):
    id: str
    prompt: str
    puml_code: str
    created_at: str


class HistoryResponse(BaseModel):
    items: list[HistoryItem]


# --- Drawings ---

class DrawingCreate(BaseModel):
    title: str = Field(default="Untitled", max_length=255)
    data: dict = Field(..., description="Excalidraw scene JSON (elements, appState, files)")
    thumbnail: str | None = Field(default=None, description="Base64 PNG data URL thumbnail")


class DrawingUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    data: dict | None = Field(default=None, description="Excalidraw scene JSON")
    thumbnail: str | None = Field(default=None, description="Base64 PNG data URL thumbnail")


class DrawingOut(BaseModel):
    id: str
    share_id: str
    title: str
    data: dict
    thumbnail: str | None
    created_at: str
    updated_at: str


class DrawingListItem(BaseModel):
    id: str
    share_id: str
    title: str
    thumbnail: str | None
    created_at: str
    updated_at: str


class DrawingListResponse(BaseModel):
    items: list[DrawingListItem]


# --- Generation Stats ---

class GenerationStatsItem(BaseModel):
    id: str
    prompt: str
    status: str
    error_message: str | None
    created_at: str


class RenderErrorReport(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    renderer: str = Field(..., pattern="^(plantuml|d2|excalidraw)$")
    error_message: str = Field(..., max_length=1000)


class GenerationStatusCounts(BaseModel):
    success: int = 0
    gemini_error: int = 0
    autofix_failed: int = 0
    mermaid_error: int = 0
    total: int = 0


class GenerationStatsResponse(BaseModel):
    counts: GenerationStatusCounts
    recent: list[GenerationStatsItem]


# --- Admin: pagination envelope ---
# First pagination convention in this codebase. Other list endpoints
# (HistoryResponse, DrawingListResponse) return a bare {items: [...]} with no
# totals; admin tables need page numbers, so they use {items, meta} instead.

class PageMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


# --- Admin: overview ---

class TrendPoint(BaseModel):
    date: str = Field(..., description="UTC calendar day, YYYY-MM-DD")
    total: int
    success: int
    failed: int


class AdminStatsResponse(BaseModel):
    total_users: int
    total_generations: int
    total_drawings: int
    total_feedback: int
    generations_24h: int
    generations_7d: int
    new_users_7d: int
    success_count: int
    failure_count: int
    failure_rate: float
    # Raw dicts rather than one field per known status: the previous version
    # hardcoded three status names and silently excluded render_error from the
    # failure rate. Anything the pipeline writes now shows up automatically.
    status_counts: dict[str, int]
    renderer_counts: dict[str, int]
    category_counts: dict[str, int]
    trend: list[TrendPoint] = Field(..., description="Last 14 UTC days, gap-filled")


# --- Admin: users ---

class AdminUserItem(BaseModel):
    id: str
    email: str
    name: str | None
    avatar_url: str | None
    oauth_provider: str
    tier: str
    created_at: str
    generation_count: int
    last_generation_at: str | None


class AdminUsersResponse(BaseModel):
    items: list[AdminUserItem]
    meta: PageMeta


# --- Admin: generations ---

class AdminGenerationItem(BaseModel):
    id: str
    prompt: str = Field(..., description="Truncated for list views")
    status: str
    renderer: str
    category: str | None
    error_message: str | None
    created_at: str
    user_id: str | None
    user_email: str | None = Field(None, description="None for anonymous generations")
    ip_address: str | None


class AdminGenerationsResponse(BaseModel):
    items: list[AdminGenerationItem]
    meta: PageMeta


class AdminGenerationDetail(AdminGenerationItem):
    """Full row for the detail view. Inherits every list field but carries the
    untruncated prompt plus the heavy columns omitted from list responses."""

    puml_code: str | None
    ir_data: dict | None
