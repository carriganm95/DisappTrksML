import os
import tensorflow as tf
from tensorflow import keras
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
import random
import sys
import pickle
from keras import optimizers, regularizers

import utils
from generator import generator
from model import buildModel


def run_validation(model, weights, batchDir, dataDir, plotDir, batch_size):
	print("------------------STARTING VALIDATION--------------------")
	model.load_weights(weights)

	# load the batches used to train and validate
	val_e_file_batches = np.load(batchDir+'e_files_valBatches.npy', allow_pickle=True)
	val_e_event_batches = np.load(batchDir+'e_events_valBatches.npy', allow_pickle=True)
	val_bkg_file_batches = np.load(batchDir+'bkg_files_valBatches.npy', allow_pickle=True)
	val_bkg_event_batches = np.load(batchDir+'bkg_events_valBatches.npy', allow_pickle=True)

	print("Define Generator")
	val_generator = generator(val_e_file_batches, val_bkg_file_batches, val_e_event_batches, val_bkg_event_batches, 
		batch_size, dataDir, True, False)
	print("Reset Generator")
	val_generator.reset()
	print("Get Predictions")
	predictions = model.predict(val_generator, verbose=2)
	true = val_generator.get_y_batches()
	print("Get Indices of Events")
	indices = val_generator.get_indices_batches()

	etas_FP, phis_FP, etas_FN, phis_FN = [], [], [], []
	cm = np.zeros((2,2)) 
	for t,pred,index in zip(true,predictions, indices):
		if(pred[1]>0.5):
			if(t[1]>0.5): 
				cm[1][1]+=1;
			else: 
				cm[1][0]+=1;

				temp = np.load(dataDir+"images_0p5_"+str(int(index[0]))+".npz")['bkg_infos']
				event = []
				for evt in temp:
					if(evt[1]==int(index[1])):
						event = evt
						break					
				assert len(event) > 0, str(index[0])+", "+str(index[1])
				etas_FP.append(event[7])
				phis_FP.append(event[8])
					
		else:
			if(t[1]>0.5): 
				cm[0][1]+=1;

				temp = np.load(dataDir+"images_0p5_"+str(int(index[0]))+".npz")['e_infos']
				event = []
				for evt in temp:
					if(evt[1]==int(index[1])):
						event = evt
						break
				assert len(event) > 0, str(index[0])+", "+str(index[1]) + ", " + str(t)
				etas_FN.append(event[7])
				phis_FN.append(event[8])

			else: cm[0][0]+=1;

	print(cm)

	utils.metrics(true[:,1], predictions[:,1], plotDir, threshold=0.5)

	print()
	print(utils.bcolors.GREEN+"Saved metrics to "+plotDir+utils.bcolors.ENDC)
	print()

	np.savez_compressed(batchDir+"etas_phis.npz",
						etas_FP = etas_FP,
						phis_FP = phis_FP,
						etas_FN = etas_FN,
						phis_FN = phis_FN)

if __name__ == "__main__":

	dataDir = "/store/user/llavezzo/disappearingTracks/converted_deepSets100_failAllRecos/"
	batchDir = "/data/users/llavezzo/deepSets100_2/deepSets100_2_p0/outputFiles/"
	plotDir = "/data/users/llavezzo/deepSets100_2/deepSets100_2_p0/"

	weights = "/data/users/llavezzo/deepSets100_2/deepSets100_2_p0/weights/lastEpoch.h5"

	model = buildModel()

	model.compile(optimizer=optimizers.Adam(), 
				  loss='categorical_crossentropy', 
				  metrics=['accuracy'])

	run_validation(model, weights, batchDir, dataDir, plotDir, 64)