"""Test Balochi, English or both with a recorded audio clip. NO MOTOR CONNECTION."""
import argparse,json
from pathlib import Path
from recognizer import BilingualRecognizer

p=argparse.ArgumentParser()
p.add_argument('file')
p.add_argument('--mode',choices=['auto','english','balochi'],default='auto')
p.add_argument('--vosk-model',default=None,help='Directory of existing English Vosk model')
args=p.parse_args()
r=BilingualRecognizer(model_path=args.vosk_model)
print('SYSTEM:',json.dumps(r.status(),indent=2))
print('RESULT:',json.dumps(r.analyze(Path(args.file).read_bytes(),args.mode),indent=2))
