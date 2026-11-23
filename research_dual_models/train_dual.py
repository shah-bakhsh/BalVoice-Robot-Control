"""Train two genuine Balochi command classifiers from the provided audios.zip.
Models: temporal-MFCC SVM and lightweight log-mel CNN. Offline CPU training.
This is NOT an autonomous driving release. Unseen-voice and real-world validation required.
"""
from __future__ import annotations
import json, random, time, copy, argparse
from pathlib import Path
from collections import Counter
import numpy as np
import joblib
import torch
from torch import nn
from torch.utils.data import TensorDataset,DataLoader
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from balochi_features import LABEL_TO_COMMAND

ROOT=Path(__file__).parent
LABELS=sorted(LABEL_TO_COMMAND)

def set_seed(seed):
 random.seed(seed); np.random.seed(seed);torch.manual_seed(seed)

class SmallSpeechCNN(nn.Module):
 def __init__(self,classes=6):
  super().__init__()
  self.layers=nn.Sequential(
   nn.Conv2d(1,16,3,padding=1),nn.BatchNorm2d(16),nn.ReLU(),nn.MaxPool2d(2),
   nn.Conv2d(16,32,3,padding=1),nn.BatchNorm2d(32),nn.ReLU(),nn.MaxPool2d(2),
   nn.Conv2d(32,48,3,padding=1),nn.BatchNorm2d(48),nn.ReLU(),nn.MaxPool2d(2),
   nn.AdaptiveAvgPool2d((3,6)), nn.Flatten(),nn.Dropout(0.25),
   nn.Linear(48*3*6,96),nn.ReLU(),nn.Dropout(0.25),nn.Linear(96,classes))
 def forward(self,x): return self.layers(x)

def train_cnn(X,y,idx_train,idx_val=None,epochs=65,seed=42,verbose=False):
 set_seed(seed)
 torch.set_num_threads(min(3,torch.get_num_threads()))
 model=SmallSpeechCNN(len(LABELS))
 optim=torch.optim.AdamW(model.parameters(),lr=.0015,weight_decay=.02)
 lossfn=nn.CrossEntropyLoss()
 ds=TensorDataset(torch.tensor(X[idx_train,None,:,:],dtype=torch.float32),torch.tensor(y[idx_train],dtype=torch.long))
 loader=DataLoader(ds,batch_size=24,shuffle=True,drop_last=False)
 xv=torch.tensor(X[idx_val,None,:,:],dtype=torch.float32) if idx_val is not None else None
 yv=torch.tensor(y[idx_val],dtype=torch.long) if idx_val is not None else None
 bestloss=1e6;best=None;patience=0;bestepoch=0
 for epoch in range(epochs):
  model.train()
  for xb,yb in loader:
   # Training-only small augmentation; inference untouched.
   if random.random()<.85:
    xb=xb + 0.025*torch.randn_like(xb)
   if random.random()<.5:
    xb=torch.roll(xb,random.randint(-4,4),dims=3)
   if random.random()<.35:
    c=random.randint(0,56);xb[:,:,:,c:c+8]=0
   pred=model(xb)
   loss=lossfn(pred,yb)
   optim.zero_grad();loss.backward(); optim.step()
  model.eval()
  if xv is not None:
   with torch.inference_mode():
    val_loss=lossfn(model(xv),yv).item()
   if val_loss < bestloss-0.002:
    bestloss=val_loss; best=copy.deepcopy(model.state_dict());bestepoch=epoch+1;patience=0
   else:patience+=1
   if patience>=15:break
  if verbose and (epoch+1)%10==0: print('CNN epoch',epoch+1,'val loss',round(val_loss,3) if xv is not None else 'n/a',flush=True)
 if best is not None:model.load_state_dict(best)
 return model,bestepoch if best else epochs

def predict_cnn(model, X, ids):
 model.eval()
 with torch.inference_mode():
  logits=model(torch.tensor(X[ids,None,:,:],dtype=torch.float32))
  return torch.softmax(logits,dim=1).numpy()

def stats(y, probs, labels, tag):
 pred=np.argmax(probs,axis=1)
 correct=pred==y
 conf=probs.max(axis=1)
 print(f'{tag}: {correct.mean():.3f} ({correct.sum()}/{len(y)})',flush=True)
 for t in [0.50,0.60,0.70,0.80,0.90]:
  chosen=conf>=t
  print(f'  p>={t:.2f}: {chosen.sum()}/{len(y)} ; accepted accuracy {correct[chosen].mean():.3f}' if chosen.any() else f'  p>={t:.2f}: 0/{len(y)}',flush=True)
 return {'accuracy':round(float(correct.mean()),4),'n':len(y),'correct':int(correct.sum()),'report':classification_report(y,pred,target_names=labels,zero_division=0,output_dict=True),'confusion':confusion_matrix(y,pred,labels=list(range(len(labels)))).tolist()}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--epochs',type=int,default=65);ap.add_argument('--crossval',type=int,default=3);args=ap.parse_args()
 d=np.load(ROOT/'cache/data.npz')
 f=d['mfcc']; mel=d['mel']; texts=d['label']; formats=d['format'];y=np.array([LABELS.index(t) for t in texts]); ids=np.arange(len(y))
 print('Found',len(y),'recordings, classes',LABELS,flush=True)
 svm=lambda:make_pipeline(StandardScaler(),SVC(C=100,class_weight='balanced',kernel='rbf',probability=True,random_state=42))
 splits=StratifiedKFold(args.crossval,shuffle=True,random_state=42)
 outs_svm=np.zeros((len(y),len(LABELS)),dtype='float32'); outs_cnn=np.zeros_like(outs_svm)
 cv_info=[]
 for fold,(tr,te) in enumerate(splits.split(f,y),1):
  print('FOLD',fold,'TRAIN',len(tr),'TEST',len(te),flush=True)
  model=svm();model.fit(f[tr],texts[tr]);out=model.predict_proba(f[te]); outs_svm[te]=out[:,[list(model.classes_).index(l) for l in LABELS]]
  tr2,va=train_test_split(tr,test_size=.20,stratify=y[tr],random_state=1234+fold)
  cnn,be=train_cnn(mel,y,tr2,va,epochs=args.epochs,seed=42+fold,verbose=False)
  out=predict_cnn(cnn,mel,te);outs_cnn[te]=out
  sv_acc=(outs_svm[te].argmax(1)==y[te]).mean();cnn_acc=(out.argmax(1)==y[te]).mean()
  print(f'  accuracy SVM {sv_acc:.3f}, CNN {cnn_acc:.3f} (best epoch {be})',flush=True)
  cv_info.append({'fold':fold,'svm_accuracy':float(sv_acc),'cnn_accuracy':float(cnn_acc),'cnn_best_epoch':int(be)})
 results={'dataset':{'total':len(y),'labels':dict(Counter(texts)),'formats':dict(Counter(formats)),'notes':'No speaker metadata; cross-validation splits may share speakers, cannot infer deployment accuracy.'},'folds':cv_info}
 results['svm_cv']=stats(y,outs_svm,LABELS,'SVM shuffled CV');results['cnn_cv']=stats(y,outs_cnn,LABELS,'CNN shuffled CV')
 # Strict source-shift test SVM (no leakage across recording formats)
 for tr_fmt,te_fmt in [('.ogg','.wav'),('.wav','.ogg')]:
  tr=ids[formats==tr_fmt];te=ids[formats==te_fmt]
  model=svm();model.fit(f[tr],texts[tr]);p=model.predict_proba(f[te]); p=p[:,[list(model.classes_).index(l) for l in LABELS]]
  results[f'svm_{tr_fmt}_to_{te_fmt}']=stats(y[te],p,LABELS,f'SVM format-shift {tr_fmt} -> {te_fmt}')
 # No evaluation on final trained models; save both for test recordings.
 svm_final=svm();svm_final.fit(f,texts)
 joblib.dump({'pipeline':svm_final,'class_to_command':LABEL_TO_COMMAND,'sample_rate':16000,'version':'Dual-model SVM v1, experimental, recognition only'},ROOT/'balochi_svm_final.joblib',compress=3)
 # split a tuning holdout (no voice metadata available), then final refit all with chosen training epochs
 tr,va=train_test_split(ids,test_size=.20,stratify=y,random_state=2026)
 _,n_best=train_cnn(mel,y,tr,va,epochs=args.epochs,seed=42)
 final_epoch=min(max(n_best,12),args.epochs)
 net,_=train_cnn(mel,y,ids,None,epochs=final_epoch,seed=42)
 torch.save({'state_dict':net.state_dict(),'labels':LABELS,'sample_rate':16000,'mel_frames':64,'version':'Dual-model CNN v1, experimental, recognition only'},ROOT/'balochi_cnn_final.pt')
 results['final_cnn_epochs']=final_epoch
 results['model_selection']='Select using independent phone recordings; both exported as recognition-only candidates.'
 (ROOT/'evaluation.json').write_text(json.dumps(results,indent=2))
 print('SAVED both models and evaluation.json',flush=True)
if __name__=='__main__':main()
