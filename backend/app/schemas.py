from pydantic import BaseModel, Field


class RenderRequest(BaseModel):
    puml: str = Field(..., min_length=1, description="PlantUML source code")
    format: str = Field(default="svg", pattern="^(svg|png)$")


class RenderResponse(BaseModel):
    image: str = Field(..., description="Base64 data URI of the rendered diagram")
    format: str


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    context: str | None = Field(default=None, description="Previous PUML code for iteration")


class GenerateResponse(BaseModel):
    puml: str
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


class DrawingUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    data: dict | None = Field(default=None, description="Excalidraw scene JSON")


class DrawingOut(BaseModel):
    id: str
    share_id: str
    title: str
    data: dict
    created_at: str
    updated_at: str


class DrawingListItem(BaseModel):
    id: str
    share_id: str
    title: str
    created_at: str
    updated_at: str


class DrawingListResponse(BaseModel):
    items: list[DrawingListItem]
