from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    language: str = Field(default='auto', pattern='^(auto|en|hi|mr)$')
class Source(BaseModel):
    document_name: str
    page_number: int | None = None
class ChatResponse(BaseModel):
    answer: str
    language: str
    status: str
    sources: list[Source] = []
    retrieval_count: int = 0
    query_log_id: int | None = None
class FeedbackRequest(BaseModel):
    query_log_id: int
    rating: int = Field(ge=0, le=1)
    comment: str | None = Field(default=None, max_length=1000)
class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    language: str = Field(default='en', pattern='^(en|hi|mr)$')
