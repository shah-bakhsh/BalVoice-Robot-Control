import zipfile, hashlib, io, json
from pathlib import PurePosixPath, Path
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import stft
from balochi_features import decode_audio_bytes, _MEL_FILTERS, LABEL_TO_COMMAND
from balochi_v02 import extract_v02_features
from scipy.ndimage import zoom

import sys
Z=sys.argv[1] if len(sys.argv)>1 else str(Path(__file__).with_name('audios.zip'))
C=Path('cache'); C.mkdir(exist_ok=True)
labels=[]; formats=[]; names=[]; x_svm=[]; x_cnn=[]; seconds=[]; sha=[]; dupl=0; errors=[]
seen=set()
for info in zipfile.ZipFile(Z).infolist():
 p=PurePosixPath(info.filename)
 if info.is_dir() or len(p.parts)!=3 or p.parts[0]!='audio' or p.parts[1] not in LABEL_TO_COMMAND or p.suffix.lower() not in ('.ogg','.wav'):continue
 try:
  b=zipfile.ZipFile(Z).read(info)
  h=hashlib.sha256(b).hexdigest()
  if h in seen: dupl+=1;continue
  seen.add(h)
  a=decode_audio_bytes(b)
  duration=len(a)/16000
  if not (.3<=duration<=10):errors.append((info.filename,'duration:'+str(duration)));continue
  xf=extract_v02_features(a)
  x=a.astype('float32')
  r=np.sqrt(np.maximum(uniform_filter1d(x*x,size=320,mode='constant'),0))
  threshold=max(.006, r.max()*.07)
  ids=np.flatnonzero(r>threshold)
  if len(ids)>=100:
   x=x[max(0,ids[0]-800):min(len(x),ids[-1]+800)]
  x=x-np.mean(x)
  x=x/max(float(np.max(abs(x))),1.e-6)
  if len(x)<1600:x=np.pad(x,(0,1600-len(x)))
  _,_,sp=stft(x,fs=16000,nperseg=512,noverlap=352,boundary='zeros')
  feat=np.log(np.maximum(_MEL_FILTERS@np.maximum(abs(sp)**2,1e-12),1e-10))
  # interpolate time steps to 128 (preserves relative speech phases)
  inds=np.linspace(0,feat.shape[1]-1,64)
  indices=np.arange(feat.shape[1]); feat=np.stack([np.interp(inds,indices,row) for row in feat])
  feat=(feat-np.mean(feat,axis=1,keepdims=True))/(np.std(feat,axis=1,keepdims=True)+.7)
  x_cnn.append(feat.astype('float32'));x_svm.append(xf)
  labels.append(p.parts[1]); formats.append(p.suffix.lower());names.append(info.filename);seconds.append(duration);sha.append(h)
 except Exception as e:errors.append((info.filename,str(e)))
np.savez_compressed(C/'data.npz',mfcc=np.stack(x_svm), mel=np.stack(x_cnn),label=np.array(labels),format=np.array(formats),name=np.array(names),seconds=np.array(seconds), sha=np.array(sha))
from collections import Counter
print('COUNT',len(labels),'DUPL',dupl,'ERRORS',errors[:6]); print('LABELS',Counter(labels));print('FORMATS',Counter(formats)); print('DURATIONS',round(sum(seconds)/60,2),'minutes')
