from __future__ import annotations
import shutil, tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import ROOT, settings
from .database import Document, Feedback, QueryLog, SessionLocal, init_db
from .schemas import ChatRequest, ChatResponse, FeedbackRequest, TTSRequest
from . import services

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.chroma_dir.mkdir(parents=True,exist_ok=True); settings.uploads_dir.mkdir(parents=True,exist_ok=True); settings.audio_dir.mkdir(parents=True,exist_ok=True)
    app.state.mysql_ready=init_db(); yield
app=FastAPI(title='AgriVoice AI', version='1.0.0', lifespan=lifespan)

def log(question, lang, ans, status, count):
    if not SessionLocal: return None
    try:
        with SessionLocal() as s:
            row=QueryLog(question=question,language=lang,answer=ans,response_status=status,retrieval_count=count); s.add(row); s.commit(); s.refresh(row); return row.id
    except Exception: return None
@app.get('/api/health')
def health():
    try: count=services.collection().count(); chroma=True
    except Exception: count=0; chroma=False
    return {'status':'ok','mysql':bool(SessionLocal),'chromadb':chroma,'vector_count':count,'gemini_configured':bool(settings.gemini_api_key),'speech_recognition':'on_demand'}
@app.post('/api/chat',response_model=ChatResponse)
def chat(request: ChatRequest):
    ans,lang,status,src,count=services.answer(request.question,request.language)
    return ChatResponse(answer=ans,language=lang,status=status,sources=src,retrieval_count=count,query_log_id=log(request.question,lang,ans,status,count))
@app.post('/api/voice/synthesize')
async def synthesize(request: TTSRequest):
    try: return {'audio_url':await services.synthesize(request.text,request.language)}
    except Exception as e: raise HTTPException(503,f'TTS unavailable: {e}')
@app.post('/api/voice/transcribe')
async def voice_transcribe(audio: UploadFile = File(...)):
    if not (audio.content_type or '').startswith('audio/'): raise HTTPException(415,'Upload an audio file.')
    suffix=Path(audio.filename or 'audio.webm').suffix or '.webm'
    with tempfile.NamedTemporaryFile(suffix=suffix,delete=False) as f: shutil.copyfileobj(audio.file,f); tmp=Path(f.name)
    try:
        text,lang=await services.transcribe(tmp); return {'transcript':text,'language':lang,'language_name':{'en':'English','hi':'Hindi','mr':'Marathi'}[lang],'status':'success'}
    finally: tmp.unlink(missing_ok=True)
@app.post('/api/voice/ask')
async def voice_ask(audio: UploadFile = File(...)):
    result=await voice_transcribe(audio); ans,lang,status,src,count=services.answer(result['transcript'],result['language']); audio_url=None
    if status=='answered':
        try: audio_url=await services.synthesize(ans,lang)
        except Exception: pass
    return {'transcript':result['transcript'],'detected_language':lang,'answer':ans,'status':status,'sources':src,'retrieval_count':count,'audio_url':audio_url}
@app.post('/api/documents/upload')
async def upload_document(file: UploadFile = File(...)):
    if Path(file.filename or '').suffix.lower()!='.pdf': raise HTTPException(415,'Only PDF files are accepted.')
    with tempfile.NamedTemporaryFile(suffix='.pdf',delete=False) as f: shutil.copyfileobj(file.file,f); tmp=Path(f.name)
    try:
        doc_id,n,duplicate=services.ingest(tmp,file.filename or 'document.pdf')
        if SessionLocal and not duplicate:
            with SessionLocal() as s: s.merge(Document(id=doc_id,filename=file.filename or '',original_filename=file.filename or '',file_hash=doc_id,file_path=str(settings.uploads_dir),status='indexed')); s.commit()
        return {'document_id':doc_id,'status':'already_indexed' if duplicate else 'indexed','chunk_count':n}
    finally: tmp.unlink(missing_ok=True)
@app.get('/api/documents')
def list_documents():
    col=services.collection(); data=col.get(include=['metadatas']); docs={}
    for m in data['metadatas']:
        docs[m['document_id']]={'id':m['document_id'],'filename':m.get('document_name'),'status':'indexed'}
    return list(docs.values())
@app.delete('/api/documents/{document_id}')
def delete_document(document_id: str):
    services.collection().delete(where={'document_id':document_id})
    if SessionLocal:
        with SessionLocal() as s: row=s.get(Document,document_id); row and s.delete(row); s.commit()
    return {'status':'deleted'}
@app.post('/api/feedback')
def feedback(request: FeedbackRequest):
    if not SessionLocal: raise HTTPException(503,'MySQL is unavailable.')
    with SessionLocal() as s: s.add(Feedback(**request.model_dump())); s.commit()
    return {'status':'recorded'}
@app.get('/api/audio/{name}')
def audio(name: str):
    p=settings.audio_dir/Path(name).name
    if not p.exists(): raise HTTPException(404,'Audio not found')
    return FileResponse(p,media_type='audio/mpeg')
app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
@app.get('/')
def home(): return FileResponse(ROOT/'frontend'/'index.html')
