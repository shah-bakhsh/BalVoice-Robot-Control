"""Private phone microphone testing. Intentionally NO motor/serial code."""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,File,Form,UploadFile,HTTPException
from fastapi.responses import HTMLResponse
from dual_recognizer import BilingualTester

logging.basicConfig(level=logging.INFO,format='%(asctime)s | %(message)s',datefmt='%H:%M:%S')
log=logging.getLogger('balochi-model-test')
instance=None
@asynccontextmanager
async def lifespan(app):
 global instance
 instance=BilingualTester()
 log.info('MODELS READY | BALOCHI SVM + CNN | ENGLISH %s | ARDUINO DISABLED', 'ON' if instance.vosk else 'OFF')
 yield
 log.info('SHUTDOWN')
app=FastAPI(lifespan=lifespan)
@app.get('/',response_class=HTMLResponse)
def home():return Path(__file__).with_name('index.html').read_text(encoding='utf-8')
@app.get('/health')
def health():return {'server':'ready','balochi_svm':True,'balochi_cnn':True,'english_vosk':bool(instance and instance.vosk),'arduino_connected':False,'motors_enabled':False}
@app.post('/recognize')
async def recognize(file:UploadFile=File(...),mode:str=Form('balochi')):
 if instance is None:raise HTTPException(503,'Models loading')
 audio=await file.read(6_000_001)
 try:
  result=instance.recognize(audio,mode)
 except Exception as exc:
  log.error('VOICE ERROR | %s | NO MOTOR COMMAND',exc)
  raise HTTPException(400,str(exc))
 b=result.get('balochi_models') or {}
 c=b.get('cnn') or {};s=b.get('svm') or {}
 log.info('VOICE | %s | %s -> %s | CNN=%s (%.3f) | SVM=%s (%.3f) | Arduino=OFF',mode.upper(),result.get('recognized') or 'not recognized',result.get('candidate_action') or 'REJECTED',c.get('phrase','-'),c.get('score',0),s.get('phrase','-'),s.get('score',0))
 return result
