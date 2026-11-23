"""Compare two trained Balochi command models. No serial/motor code.
These uncalibrated classifiers are experimental, not safe to authorize movement.
"""
from __future__ import annotations
import json, os, re
from pathlib import Path
import joblib
import numpy as np
from balochi_features import decode_audio_bytes, decode_audio_file, LABEL_TO_COMMAND
from balochi_v02 import extract_v02_features
from cnn_runtime import CNNRuntime,logmel_for_cnn

ROOT=Path(__file__).resolve().parent
ACTIONS={'S':'STOP','F':'FORWARD','B':'BACKWARD','L':'LEFT','R':'RIGHT'}
ENGLISH={
 'stop':'S','halt':'S','stop robot':'S','stop car':'S',
 'forward':'F','move forward':'F','go forward':'F','go ahead':'F',
 'backward':'B','backwards':'B','move backward':'B','go backward':'B','reverse':'B',
 'left':'L','turn left':'L','move left':'L','go left':'L',
 'right':'R','turn right':'R','move right':'R','go right':'R',
}

class DualBalochi:
 def __init__(self):
  path=ROOT/'balochi_svm_final.joblib'
  self.svm=joblib.load(path)['pipeline']  # load only trusted files
  self.cnn=CNNRuntime(ROOT/'balochi_cnn_numpy.npz')
 def predict(self,audio):
  x=extract_v02_features(audio).reshape(1,-1)
  p_svm=self.svm.predict_proba(x)[0]
  ordered=list(self.svm.classes_)
  lab_svm=str(ordered[int(np.argmax(p_svm))]); score_svm=float(max(p_svm))
  p_cnn=self.cnn.probabilities(logmel_for_cnn(audio))
  lab_cnn=self.cnn.labels[int(np.argmax(p_cnn))];score_cnn=float(max(p_cnn))
  agree=lab_svm==lab_cnn
  # Scores are NOT calibrated across devices. This is a demonstration, not authorization.
  candidate=lab_cnn if agree and lab_cnn!='noise' else None
  code=LABEL_TO_COMMAND.get(candidate)
  return {
   'language':'balochi',
   'svm':{'phrase':lab_svm,'score':round(score_svm,3)},
   'cnn':{'phrase':lab_cnn,'score':round(score_cnn,3)},
   'models_agree':bool(agree),
   'candidate_phrase':candidate,
   'candidate_action':ACTIONS.get(code),
   'candidate_arduino_code':code,
   'accepted_for_motor':False,
   'reason':('Both models agree; offline test only' if candidate else 'Models disagree or detect noise; no action'),
   'arduino':'DISABLED — no motor commands sent'
  }

class BilingualTester:
 def __init__(self):
  self.balochi=DualBalochi()
  self.vosk=None;self.english_error=None
  try:
   from vosk import Model,SetLogLevel
   SetLogLevel(-1)
   path=Path(os.environ.get('VOSK_MODEL_PATH',str(Path.home()/'robot-live-voice/models/vosk-model-small-en-us-0.15'))).expanduser()
   if path.exists():self.vosk=Model(str(path))
   else:self.english_error=f'English Vosk model folder missing: {path}'
  except ImportError:self.english_error='vosk Python package not installed'
  except Exception as exc:self.english_error=f'{type(exc).__name__}: {exc}'
 def english(self,audio,mode='english'):
  if self.vosk is None:
   return {'language':'english','phrase':'','accepted':False,'reason':self.english_error,'score':0.0,'candidate_arduino_code':None,'candidate_action':None,'accepted_for_motor':False}
  from vosk import KaldiRecognizer
  if mode=='english':
   grammar=json.dumps(list(ENGLISH)+['[unk]'])
   rec=KaldiRecognizer(self.vosk,16000,grammar)
  else:rec=KaldiRecognizer(self.vosk,16000)
  rec.SetWords(True)
  rec.AcceptWaveform((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
  resp=json.loads(rec.FinalResult())
  phrase=' '.join(re.sub('[^a-z ]',' ',(resp.get('text') or '').lower()).split())
  words=resp.get('result') or []
  score=float(np.mean([w.get('conf',0) for w in words])) if words else 0.
  code=ENGLISH.get(phrase)
  ok=code is not None and score >= (.65 if mode=='english' else .86)
  return {'language':'english','phrase':phrase,'score':round(score,3),'accepted':bool(ok),'candidate_action':ACTIONS.get(code) if ok else None,'candidate_arduino_code':code if ok else None,'accepted_for_motor':False,'reason':'Recognized for testing only' if ok else 'Unknown or low-confidence English phrase'}
 def recognize(self,data,mode='balochi'):
  if mode not in ('balochi','english','auto'):raise ValueError('Choose balochi, english, or auto')
  if not data or len(data)>6_000_000:raise ValueError('Audio is empty or too large')
  audio=decode_audio_bytes(data)
  length=len(audio)/16000
  if not .4<=length<=8.0:raise ValueError('Record one short command (0.4–8 seconds)')
  if float(np.sqrt(np.mean(np.asarray(audio,dtype='float64')**2)))<0.003:
   return {'mode':mode,'status':'REJECTED','reason':'Silent or too quiet','motor_control_enabled':False}
  bs=self.balochi.predict(audio) if mode in ('balochi','auto') else None
  eng=self.english(audio,mode) if mode in ('english','auto') else None
  if mode=='balochi':
   ok=bool(bs['candidate_arduino_code']);target=bs['candidate_arduino_code'];phrase=bs['candidate_phrase'];lang='balochi'
  elif mode=='english':
   ok=eng['accepted'];target=eng.get('candidate_arduino_code');phrase=eng.get('phrase');lang='english'
  else:
   # Uncertain bilingual automatic language selection: reject ambiguous cases.
   e=eng['candidate_arduino_code'] if eng['accepted'] else None
   b=bs['candidate_arduino_code']
   if e and b and e!=b:ok=False;target=None;phrase=None;lang=None
   elif e:ok=True;target=e;phrase=eng['phrase'];lang='english'
   elif b:ok=True;target=b;phrase=bs['candidate_phrase'];lang='balochi'
   else:ok=False;target=None;phrase=None;lang=None
  return {'mode':mode,'status':'CANDIDATE (TEST ONLY)' if ok else 'REJECTED','recognized':phrase,'language':lang,
          'candidate_action':ACTIONS.get(target),'candidate_arduino_code':target,
          'balochi_models':bs,'english_model':eng,'motor_control_enabled':False,
          'message':'This package NEVER opens a serial port or sends motor commands'}
