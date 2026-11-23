"""Train the experimental Balochi classifier from audios.zip (no audio extracted).

Example: python train_balochi.py audios.zip
This is an exploratory benchmark; for reliable deployment obtain independent
speaker IDs and evaluate on fresh Android-recorded speech.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import joblib
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from balochi_features import decode_audio_bytes, LABEL_TO_COMMAND
from balochi_v02 import extract_v02_features


def load_zip(path):
    X, y, seen = [], [], set()
    with ZipFile(path) as z:
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            if info.is_dir() or len(p.parts) != 3 or p.parts[0] != 'audio' or p.parts[1] not in LABEL_TO_COMMAND or p.suffix.lower() not in {'.ogg','.wav','.webm'}:
                continue
            data = z.read(info)
            digest = hashlib.sha256(data).digest()
            if digest in seen:
                continue
            seen.add(digest)
            audio = decode_audio_bytes(data)
            if .3 <= len(audio)/16000 <= 10:
                X.append(extract_v02_features(audio))
                y.append(p.parts[1])
    if len(set(y)) < 6 or min(y.count(k) for k in set(y)) < 10:
        raise ValueError('Expected all six folders with at least ten recordings each')
    return np.stack(X), np.asarray(y)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('dataset_zip', type=Path)
    parser.add_argument('--output', default='balochi_model_v02.joblib')
    args=parser.parse_args()
    X,y=load_zip(args.dataset_zip)
    # SVC probability scores are approximate; not a guarantee of real-world reliability.
    cv=StratifiedKFold(n_splits=5,shuffle=True,random_state=42)
    model=make_pipeline(StandardScaler(),SVC(C=100,class_weight='balanced',probability=True,random_state=42))
    probabilities=cross_val_predict(model,X,y,cv=cv,method='predict_proba')
    labels=np.unique(y)
    predictions=labels[probabilities.argmax(axis=1)]
    print('Recordings:',len(y),'Labels:',list(labels))
    print('Shuffled 5-fold CV accuracy:', round(accuracy_score(y,predictions),4))
    print(classification_report(y,predictions,zero_division=0))
    print('CAUTION: recordings can share speakers and microphones; this is NOT a new-speaker evaluation.')
    for threshold in (0.5,0.7,0.8,0.9):
        keep=probabilities.max(axis=1) >= threshold
        score=round(float(accuracy_score(y[keep],predictions[keep])),3) if keep.any() else 'N/A'
        print('threshold',threshold,'accepted',int(keep.sum()),'of',len(y),'accuracy among accepted',score)
    model.fit(X,y)
    joblib.dump({'pipeline':model,'model_version':'Balochi MFCC-SVM v0.2 EXPERIMENTAL',
                 'class_to_command':LABEL_TO_COMMAND,'sample_rate':16000},args.output,compress=3)
    print('Saved',args.output,'(recognition only, no motor support)')

if __name__=='__main__':
    main()
