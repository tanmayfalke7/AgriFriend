from __future__ import annotations
import asyncio, hashlib, re, shutil, time, uuid
from pathlib import Path
import chromadb, fitz
from fastapi import HTTPException
from sentence_transformers import SentenceTransformer
from .config import settings

MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
COLLECTION = 'agricultural_knowledge'
_model = None
def model():
    global _model
    if _model is None: _model = SentenceTransformer(MODEL)
    return _model
def collection(): return chromadb.PersistentClient(path=str(settings.chroma_dir)).get_or_create_collection(COLLECTION)
def language_for(text: str) -> str:
    if re.search(r'[\u0900-\u097F]', text): return 'hi' if any(x in text for x in 'की है में क्या') else 'mr'
    return 'en'
def fallback(lang: str) -> str:
    return {'mr':'माफ करा, उपलब्ध माहितीनुसार खात्रीशीर उत्तर देता येत नाही. कृपया स्थानिक कृषी तज्ज्ञांचा सल्ला घ्या.', 'hi':'माफ कीजिए, उपलब्ध जानकारी के आधार पर भरोसेमंद उत्तर नहीं दिया जा सकता। कृपया स्थानीय कृषि विशेषज्ञ से संपर्क करें.'}.get(lang, 'I cannot provide a reliable answer from the available approved documents. Please consult a local agricultural expert.')
def retrieve(question: str, n: int = 5):
    col = collection()
    if not col.count(): return []
    embedding = model().encode([question], normalize_embeddings=True).tolist()
    raw = col.query(query_embeddings=embedding, n_results=min(n, col.count()), include=['documents','metadatas','distances'])
    return [{'text': d, 'metadata': m, 'distance': float(x)} for d,m,x in zip(raw['documents'][0], raw['metadatas'][0], raw['distances'][0])]
def sources(results):
    seen=set(); out=[]
    for item in results:
        m=item['metadata']; key=(m.get('document_name'),m.get('page_number'))
        if key not in seen: out.append({'document_name':m.get('document_name','Unknown'), 'page_number':m.get('page_number')}); seen.add(key)
    return out
def answer(question: str, requested_language: str):
    lang = language_for(question) if requested_language == 'auto' else requested_language
    results = retrieve(question)
    good = [r for r in results if r['distance'] <= settings.retrieval_distance_threshold]
    if len(good) < 1: return fallback(lang), lang, 'refused', [], 0
    if not settings.gemini_api_key: return fallback(lang), lang, 'refused', sources(good), len(results)
    evidence='\n\n'.join(f"[{r['metadata'].get('document_name')} p.{r['metadata'].get('page_number')}] {r['text']}" for r in good)
    prompt=f'''You are AgriVoice AI, a cautious agricultural assistant. Answer only from the evidence below. Do not invent chemical dosages, prices, weather, scheme eligibility, facts or citations. If evidence is insufficient, say so. Give a short practical answer in {lang}.\n\nQUESTION: {question}\n\nEVIDENCE:\n{evidence}'''
    try:
        from google import genai
        client=genai.Client(api_key=settings.gemini_api_key)
        response=client.models.generate_content(model=settings.gemini_model, contents=prompt)
        text=(response.text or '').strip()
        if not text: raise ValueError('empty Gemini response')
        return text, lang, 'answered', sources(good), len(results)
    except Exception: return fallback(lang), lang, 'refused', sources(good), len(results)
def chunk(text, size=2800, overlap=400):
    text=re.sub(r'\s+',' ',text).strip(); out=[]; start=0
    while start < len(text):
        end=min(len(text),start+size); boundary=text.rfind('. ',start+size//2,end)
        if boundary > start: end=boundary+1
        if text[start:end].strip(): out.append(text[start:end].strip())
        if end >= len(text): break
        start=max(start+1,end-overlap)
    return out
def ingest(pdf: Path, original_name: str):
    digest=hashlib.sha256(pdf.read_bytes()).hexdigest(); col=collection()
    if col.get(where={'document_hash':digest}, include=[])['ids']: return digest, 0, True
    doc=fitz.open(pdf); rows=[]
    for p,page in enumerate(doc,1): rows.extend((x,p) for x in chunk(page.get_text()) )
    doc.close()
    if not rows: raise HTTPException(422, 'No extractable text found; this scanned PDF needs OCR.')
    texts=[x[0] for x in rows]; emb=model().encode(texts,normalize_embeddings=True).tolist()
    col.add(ids=[f'{digest[:16]}-{i:04d}' for i in range(len(texts))], documents=texts, embeddings=emb, metadatas=[{'document_id':digest,'document_hash':digest,'document_name':original_name,'source':original_name,'page_number':p,'chunk_index':i,'language':'en'} for i,(_,p) in enumerate(rows)])
    settings.uploads_dir.mkdir(parents=True,exist_ok=True); shutil.copy2(pdf,settings.uploads_dir/f'{digest[:16]}_{original_name}')
    return digest,len(texts),False
async def synthesize(text: str, lang: str):
    import edge_tts
    voices={'en':'en-IN-NeerjaNeural','hi':'hi-IN-SwaraNeural','mr':'mr-IN-AarohiNeural'}
    settings.audio_dir.mkdir(parents=True,exist_ok=True); name=f'{uuid.uuid4().hex}.mp3'; path=settings.audio_dir/name
    await edge_tts.Communicate(text, voices.get(lang, voices['en'])).save(str(path))
    return f'/api/audio/{name}'
async def transcribe(path: Path):
    try:
        from faster_whisper import WhisperModel
        segments, info=WhisperModel(settings.whisper_model, device='cpu', compute_type='int8').transcribe(str(path))
        text=' '.join(s.text.strip() for s in segments).strip()
        if not text: raise ValueError('No speech detected')
        return text, (info.language if info.language in {'en','hi','mr'} else 'en')
    except ImportError: raise HTTPException(503,'Speech recognition dependency is not installed.')
