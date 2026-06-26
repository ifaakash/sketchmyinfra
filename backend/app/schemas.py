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
    context: str | None = Field(default=None, description="Previous diagram code for iteration")
    context_renderer: str | None = Field(default=None, description="Renderer of the context diagram")


class GenerateResponse(BaseModel):
    renderer: str = Field(default="plantuml", description="Renderer used: plantuml or mermaid")
    code: str = Field(..., description="Diagram source code (PlantUML or Mermaid)")
    prompt_used: str
    puml: str | None = Field(default=None, description="PlantUML code (backward compat, only when renderer=plantuml)")


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
    renderer: str = Field(..., pattern="^(plantuml|mermaid)$")
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


# --- Admin Stats ---

class AdminStatsResponse(BaseModel):
    total_users: int
    total_generations: int
    generations_24h: int
    generations_7d: int
    success_count: int
    gemini_error_count: int
    autofix_failed_count: int
    mermaid_error_count: int = 0
    failure_rate: float
    recent_failures: list[GenerationStatsItem]
