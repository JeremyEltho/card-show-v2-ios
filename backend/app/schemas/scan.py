from pydantic import BaseModel


class ScanRequest(BaseModel):
    ocr_text: str | None = None
    ocr_confidence: float | None = None
    image_b64: str | None = None


class CardCandidate(BaseModel):
    card_id: str
    name: str
    set_name: str | None = None
    confidence: float


class ScanResponse(BaseModel):
    card_id: str
    name: str
    set_name: str | None = None
    number: str | None = None
    image_url_sm: str | None = None
    confidence: float
    market_price: float | None = None
    pipeline: str


class ScanFailResponse(BaseModel):
    detail: str
    candidates: list[CardCandidate] = []
