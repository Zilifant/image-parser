from typing import Literal, Optional

from pydantic import BaseModel, Field

Point = tuple[float, float]


class DetectParams(BaseModel):
    # Fraction of page area below which a blob is discarded.
    min_area_frac: float = Field(0.0002, ge=0.0, le=1.0)
    # Fraction of page area above which a blob is discarded (e.g. a full-page frame).
    max_area_frac: float = Field(0.9, ge=0.0, le=1.0)
    # Pixel radius used to bridge nearby strokes and merge adjacent blobs.
    # 0 = auto-scale from image width.
    merge_radius: int = Field(0, ge=0, le=100)
    # Adaptive threshold parameters.
    block_size: int = Field(51, ge=3, le=201)
    c: int = Field(12, ge=-50, le=50)
    mode: Literal["adaptive", "otsu"] = "adaptive"


RegionStatus = Literal["provisional", "approved", "flagged"]


class Region(BaseModel):
    id: str
    bbox: tuple[int, int, int, int]  # x, y, w, h
    polygon: list[Point]
    source: Literal["auto", "manual", "sam", "merge"]
    confidence: float = 1.0
    enabled: bool = True
    label: str = ""
    has_mask: bool = False
    status: RegionStatus = "provisional"
    qc_issues: list[str] = []


class RegionPatch(BaseModel):
    polygon: Optional[list[Point]] = None
    enabled: Optional[bool] = None
    label: Optional[str] = None
    status: Optional[RegionStatus] = None


class PolygonCreate(BaseModel):
    polygon: list[Point] = Field(min_length=3)


class MergeRequest(BaseModel):
    region_ids: list[str] = Field(min_length=2)


class SplitRequest(BaseModel):
    params: Optional[DetectParams] = None


class ExportOptions(BaseModel):
    style: Literal["ink", "binary"] = "ink"
    # pure_white is the default: the target output is white artwork on
    # transparency (see the project brief).
    rgb: Literal["pure_white", "original", "pure_black"] = "pure_white"
    padding: int = Field(4, ge=0, le=64)


class PageExportRequest(ExportOptions):
    region_ids: Optional[list[str]] = None  # None = all enabled regions


class BatchExportRequest(ExportOptions):
    out_dir: Optional[str] = None


class DetectRequest(BaseModel):
    params: Optional[DetectParams] = None


class PageSummary(BaseModel):
    id: str
    name: str
    width: int
    height: int
    region_count: int
    export_count: int


class Page(PageSummary):
    regions: list[Region]
    detect_params: DetectParams
    source_path: Optional[str] = None


class Project(BaseModel):
    id: str
    name: str
    created_at: str
    pages: list[PageSummary] = []


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)


class FromPathsRequest(BaseModel):
    paths: Optional[list[str]] = None
    dir: Optional[str] = None


class FsEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    is_image: bool


class JobStatus(BaseModel):
    id: str
    kind: str
    status: Literal["running", "done", "error"]
    done: int = 0
    total: int = 0
    error: Optional[str] = None


class Profile(BaseModel):
    name: str = Field(min_length=1)
    builtin: bool = False
    detect: DetectParams = DetectParams()
    export: ExportOptions = ExportOptions()


class ToolsStatus(BaseModel):
    sam: bool
    potrace: bool


class SamPoint(BaseModel):
    x: float
    y: float
    label: int = 1  # 1 = foreground, 0 = background


class SamPredictRequest(BaseModel):
    points: Optional[list[SamPoint]] = None
    box: Optional[tuple[float, float, float, float]] = None  # x, y, w, h
