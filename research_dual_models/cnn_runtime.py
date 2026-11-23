"""Small log-mel CNN, pure NumPy inference (no PyTorch required on Raspberry Pi).
Weights originate from a PyTorch-trained model. The architecture is fixed.
"""
from __future__ import annotations
from math import ceil, floor
from pathlib import Path
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.ndimage import uniform_filter1d
from scipy.signal import stft
from balochi_features import _MEL_FILTERS


def logmel_for_cnn(raw):
    x=np.asarray(raw,dtype=np.float32)
    if x.ndim!=1 or x.size==0:
        raise ValueError('Expected nonempty mono audio')
    power=uniform_filter1d(x*x,size=320,mode='constant')
    rms=np.sqrt(np.maximum(power,0))
    threshold=max(.006,float(rms.max())*.07)
    voiced=np.flatnonzero(rms>threshold)
    if len(voiced)>=100:
        x=x[max(0,int(voiced[0])-800):min(len(x),int(voiced[-1])+800)]
    x=x-np.mean(x)
    x=x/max(float(np.max(abs(x))),1e-6)
    if len(x)<1600:
        x=np.pad(x,(0,1600-len(x)))
    _,_,spectrum=stft(x,fs=16000,nperseg=512,noverlap=352,boundary='zeros')
    feat=np.log(np.maximum(_MEL_FILTERS@np.maximum(abs(spectrum)**2,1e-12),1e-10))
    times=np.linspace(0,feat.shape[1]-1,64)
    bins=np.arange(feat.shape[1]);feat=np.stack([np.interp(times,bins,row) for row in feat])
    feat=(feat-np.mean(feat,axis=1,keepdims=True))/(np.std(feat,axis=1,keepdims=True)+.7)
    return feat.astype('float32')


def _conv(x,w,b):
    # x=(channels,h,w), w=(out,in,3,3)
    padded=np.pad(x,((0,0),(1,1),(1,1)))
    patches=sliding_window_view(padded,(3,3),axis=(1,2))
    return (np.einsum('cijab,ocab->oij',patches,w,optimize=True)+b[:,None,None]).astype('float32')


def _bn(x,w,b,mean,var,eps=1e-5):
    return ((x-mean[:,None,None])/(np.sqrt(var+eps)[:,None,None])*w[:,None,None]+b[:,None,None]).astype('float32')


def _pool2(x):
    c,h,w=x.shape
    return x[:,:h//2*2,:w//2*2].reshape(c,h//2,2,w//2,2).max(axis=(2,4))


def _adaptive_avg(x,hh=3,ww=6):
    c,h,w=x.shape
    out=np.empty((c,hh,ww),dtype='float32')
    for i in range(hh):
        lo=floor(i*h/hh);hi=ceil((i+1)*h/hh)
        for j in range(ww):
            left=floor(j*w/ww);right=ceil((j+1)*w/ww)
            out[:,i,j]=x[:,lo:hi,left:right].mean(axis=(1,2))
    return out

class CNNRuntime:
    def __init__(self,path=None):
        if path is None:
            path=Path(__file__).with_name('balochi_cnn_numpy.npz')
        with np.load(path,allow_pickle=False) as z:
            self.s={k:z[k] for k in z.files if k!='labels'}
            self.labels=[str(v) for v in z['labels']]
    def probabilities(self,mel):
        x=np.asarray(mel,dtype='float32')[None,:,:]
        for idx in (0,4,8):
            prefix=f'layers.{idx}.'
            x=_conv(x,self.s[prefix+'weight'],self.s[prefix+'bias'])
            pref=f'layers.{idx+1}.'
            x=_bn(x,self.s[pref+'weight'],self.s[pref+'bias'],self.s[pref+'running_mean'],self.s[pref+'running_var'])
            x=np.maximum(x,0)
            x=_pool2(x)
        x=_adaptive_avg(x).reshape(-1)
        x=np.maximum(self.s['layers.15.weight']@x+self.s['layers.15.bias'],0)
        x=self.s['layers.18.weight']@x+self.s['layers.18.bias']
        ex=np.exp(x-x.max())
        return (ex/ex.sum()).astype('float32')
