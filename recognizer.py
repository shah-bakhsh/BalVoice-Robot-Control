"""Bilingual (English + Balochi) speech-to-command, intentionally NO motor control.

English is handled by the existing offline Vosk English model.
Balochi is handled by the trained experimental Balochi keyword classifier.
In auto mode, both may be attempted, with conservative abstention.
"""
from __future__ import annotations

import json, os, re
from pathlib import Path
from typing import Optional
import joblib
import numpy as np

from balochi_features import decode_audio_bytes, LABEL_TO_COMMAND, SAMPLE_RATE
from balochi_v02 import extract_v02_features

ROOT = Path(__file__).resolve().parent
BAL_MODEL = ROOT/'balochi_model_v02.joblib'

ENGLISH_ACTIONS = {
    'stop': 'S', 'halt': 'S', 'stop robot': 'S', 'stop car': 'S',
    'forward': 'F', 'move forward': 'F', 'go forward': 'F', 'go ahead': 'F',
    'backward': 'B', 'backwards': 'B', 'move backward': 'B', 'go backward': 'B',
    'reverse': 'B',
    'left': 'L', 'turn left': 'L', 'move left': 'L', 'go left': 'L',
    'right': 'R', 'turn right': 'R', 'move right': 'R', 'go right': 'R',
}
CODE_TO_ACTION = {'F':'forward','B':'backward','L':'left','R':'right','S':'stop'}


def english_action_from_text(text: str):
    clean = re.sub(r'[^a-z\s]', '', text.lower()).strip()
    clean = ' '.join(clean.split())
    # Exact-match the whole utterance; don't interpret unrelated speech as commands.
    return ENGLISH_ACTIONS.get(clean)


class BilingualRecognizer:
    def __init__(self, model_path: str | None = None):
        # Loading .joblib / Vosk models is safe only from trusted local files.
        self.balochi = joblib.load(BAL_MODEL)['pipeline']
        self.vosk_model = None
        self.english_error = None
        raw_path = model_path or os.environ.get('VOSK_MODEL_PATH') or str(ROOT.parent/'robot-live-voice/models/vosk-model-small-en-us-0.15')
        self.vosk_path = str(Path(raw_path).expanduser())
        try:
            from vosk import Model
            if not Path(self.vosk_path).is_dir():
                self.english_error = f'Vosk English model folder not found: {self.vosk_path}'
            else:
                self.vosk_model = Model(self.vosk_path)
        except ImportError:
            self.english_error = 'vosk Python package is not installed'
        except Exception as ex:
            self.english_error = f'Could not load English model: {type(ex).__name__}: {ex}'

    def status(self):
        return {'english_available':self.vosk_model is not None,
                'english_model_path':self.vosk_path,
                'english_issue':self.english_error,
                'balochi_available':True,
                'motor_control_enabled':False}

    def english(self,audio:np.ndarray,mode='auto'):
        if self.vosk_model is None:
            return {'language':'english','accepted':False,'reason':self.english_error or 'English model not loaded'}
        from vosk import KaldiRecognizer
        # In explicit English mode grammar helps with a small vocabulary.
        # In AUTO mode don't constrain grammar: a constrained English grammar
        # may hallucinate valid English commands on Balochi utterances.
        if mode == 'english':
            grammar=json.dumps(list(ENGLISH_ACTIONS)+['[unk]'])
            rec=KaldiRecognizer(self.vosk_model,SAMPLE_RATE,grammar)
        else:
            rec=KaldiRecognizer(self.vosk_model,SAMPLE_RATE)
        rec.SetWords(True)
        pcm=(np.clip(audio,-1,1)*32767).astype('<i2').tobytes()
        rec.AcceptWaveform(pcm)
        result=json.loads(rec.FinalResult())
        text=(result.get('text') or '').strip().lower()
        code=english_action_from_text(text)
        words=result.get('result') or []
        conf=float(np.mean([w.get('conf',0) for w in words])) if words else 0.0
        threshold=0.65 if mode=='english' else 0.86
        accepted = code is not None and conf>=threshold
        return {'language':'english','transcript':text,'candidate_arduino_code':code,
                'score':round(conf,3),'accepted':accepted,
                'reason':'accepted candidate' if accepted else 'Unrecognized phrase or low word score'}

    def balochi_predict(self,audio:np.ndarray,mode='auto'):
        features=extract_v02_features(audio).reshape(1,-1)
        scores=self.balochi.predict_proba(features)[0]
        labels=list(self.balochi.classes_)
        ranked=sorted(zip(labels,scores),key=lambda x:x[1],reverse=True)
        label, score=ranked[0]
        code=LABEL_TO_COMMAND[str(label)]
        # These are *estimated* model probabilities, not calibrated guarantees.
        threshold=0.70 if mode=='balochi' else 0.80
        accepted=(code is not None) and (float(score)>=threshold)
        return {'language':'balochi','transcript':str(label),
                'candidate_arduino_code':code,'score':round(float(score),3),
                'runner_up':str(ranked[1][0]),'accepted':bool(accepted),
                'reason':'accepted candidate' if accepted else 'Noise or uncertain Balochi prediction'}

    def analyze(self,data:bytes,mode='auto'):
        if mode not in ('auto','english','balochi'):
            raise ValueError('Mode must be auto, english, or balochi')
        if len(data)>6_000_000:
            raise ValueError('Maximum file size is 6 MB')
        audio=decode_audio_bytes(data)
        seconds=len(audio)/SAMPLE_RATE
        if not .4 <= seconds <= 8:
            raise ValueError('Speak exactly one command in a 0.4–8 second recording')
        # Pre-filter silence; peak alone is insufficient on many microphones.
        rms=float(np.sqrt(np.mean(np.asarray(audio,dtype=np.float64)**2)))
        if rms < 0.003:
            return self._rejected(mode, 'Audio is too quiet or silent')
        tested=[]
        if mode in ('english','auto'):
            tested.append(self.english(audio,mode))
        if mode in ('balochi','auto'):
            tested.append(self.balochi_predict(audio,mode))
        accepted=[r for r in tested if r.get('accepted')]
        winner=None; reason='No confident valid command was recognized'
        if mode!='auto':
            if accepted: winner=accepted[0]
        elif len(accepted)==1:
            winner=accepted[0]
        elif len(accepted)>=2:
            unique_codes={r['candidate_arduino_code'] for r in accepted}
            if len(unique_codes)==1:
                # They agree about the action, not necessarily the language.
                winner=accepted[0] if accepted[0]['score']>=accepted[1]['score'] else accepted[1]
            else:
                reason='English and Balochi recognizers disagree — rejected'
        result={'mode':mode,'accepted':bool(winner),'language_detected':winner['language'] if winner else None,
                'recognized_text':winner['transcript'] if winner else None,
                'action':CODE_TO_ACTION[winner['candidate_arduino_code']] if winner else None,
                'candidate_arduino_code':winner['candidate_arduino_code'] if winner else None,
                'recognizers':tested,'reason':'Recognized for TEST ONLY' if winner else reason,
                'motor_control_enabled':False,
                'warning':'Experimental test. Do not connect its predictions to motors.'}
        return result

    @staticmethod
    def _rejected(mode,reason):
        return {'mode':mode,'accepted':False,'language_detected':None,'recognized_text':None,
                'action':None,'candidate_arduino_code':None,'recognizers':[],
                'reason':reason,'motor_control_enabled':False}
