"""Examples: python test_dual.py recording.ogg --mode balochi / english / auto"""
import argparse,json
from pathlib import Path
from dual_recognizer import BilingualTester

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('audio_file',type=Path);p.add_argument('--mode',choices=['balochi','english','auto'],default='balochi');a=p.parse_args()
 result=BilingualTester().recognize(a.audio_file.read_bytes(),a.mode)
 print(json.dumps(result,indent=2,ensure_ascii=False))
