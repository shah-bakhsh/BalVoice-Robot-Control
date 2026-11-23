"""Export the trained CNN checkpoint as NumPy-only inference weights."""
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parent
cp=torch.load(ROOT/'balochi_cnn_final.pt',map_location='cpu',weights_only=True)
weights={key:t.detach().numpy() for key,t in cp['state_dict'].items()}
weights['labels']=np.asarray(cp['labels'])
np.savez_compressed(ROOT/'balochi_cnn_numpy.npz',**weights)
print('Exported balochi_cnn_numpy.npz')
