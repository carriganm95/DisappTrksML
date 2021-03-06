import warnings
warnings.filterwarnings('ignore')
import glob, os, sys
from datetime import datetime
import numpy as np

import tensorflow as tf
from sklearn.model_selection import KFold

from deepSetsMuons import *
from generator import *

if False:
	# limit CPU usage
	config = tf.compat.v1.ConfigProto(inter_op_parallelism_threads = 4,   
									intra_op_parallelism_threads = 4,
									allow_soft_placement = True,
									device_count={'CPU': 4})
	tf.compat.v1.keras.backend.set_session(tf.compat.v1.Session(config=config))

#######

backup_suffix = datetime.now().strftime('%Y-%m-%d_%H.%M.%S')
outdir = "train_"+backup_suffix+"/"
if(len(sys.argv)>1):
	input_params = np.load("params.npy",allow_pickle=True)[int(sys.argv[1])]
	outdir = input_params[0]

model_params = {
	'phi_layers':[256,128,64],
	'f_layers':[128,64,64],
	'maxHits' : 30,
	'track_info_shape': 5
}
val_generator_params = {
	'input_dir' : '/store/user/llavezzo/disappearingTracks/images_DYJetsToLL_v5_genmuons_bkg/',
	'batch_size' : 256,
	'with_info' : True,
	'maxHits' : 30
}
train_generator_params = val_generator_params.copy()
train_generator_params.update({
	'shuffle': True,
	'batch_ratio': 0.5
})
train_params = {
	'epochs': 10,
	'outdir':outdir,
	'patience_count':5
}

if(not os.path.isdir(outdir)): os.mkdir(outdir)

arch = DeepSetsArchitecture(**model_params)
arch.buildModel()

inputFiles = glob.glob(train_generator_params['input_dir']+'images_*.root.npz')
inputIndices = np.array([f.split('images_')[-1][:-9] for f in inputFiles])
nFiles = len(inputIndices)
print('Found', nFiles, 'input files')

file_ids = {
	'train'      : inputIndices[:300],
	'validation' : inputIndices[300:350]
}

train_generator = BalancedGenerator(file_ids['train'], **train_generator_params)
val_generator = Generator(file_ids['validation'], **val_generator_params)

arch.fit_generator(train_generator=train_generator, 
				   val_generator=val_generator, 	
					**train_params)

arch.save_trainingHistory(train_params['outdir']+'trainingHistory.pkl')
arch.plot_trainingHistory(train_params['outdir']+'trainingHistory.pkl',train_params['outdir']+'trainingHistory.png','loss')
arch.save_weights(train_params['outdir']+'model_weights.h5')
arch.save_model(train_params['outdir']+'model.h5')
arch.save_metrics(train_params['outdir']+'trainingHistory.pkl',train_params['outdir']+"metrics.pkl", train_params)