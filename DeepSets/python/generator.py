import numpy as np
from tensorflow import keras

class DataGenerator(keras.utils.Sequence):

	def __init__(self, 
				 file_ids, input_dir='.', 
				 batch_size=32, 
				 dim=(100,4), 
				 n_classes=2, 
				 shuffle=True):
		self.file_ids = file_ids
		self.input_dir = input_dir
		self.batch_size = batch_size
		self.dim = dim
		self.n_classes = n_classes
		self.shuffle = shuffle

		self.signal_data = None
		self.background_data = None
		self.num_signal = 0
		self.num_background = 0

		self.load_data()
		self.on_epoch_end()

	def load_data(self):
		for idx in self.file_ids:
			fin = np.load(self.input_dir + '/hist_' + idx + '.root.npz')
			if self.signal_data is None and self.background_data is None:
				self.signal_data = fin['signal']
				self.background_data = fin['background']
			else:
				self.signal_data = np.vstack((self.signal_data, fin['signal']))
				self.background_data = np.vstack((self.background_data, fin['background']))
		self.num_signal = self.signal_data.shape[0]
		self.num_background = self.background_data.shape[0]

	def __len__(self):
		max_signal_batches = np.floor(self.num_signal / self.batch_size)
		max_background_batches = np.floor(self.num_background / self.batch_size)
		return int(min(max_signal_batches, max_background_batches))

	def __getitem__(self, index):
		return self.__data_generation(index)

	def on_epoch_end(self):
		if self.shuffle:
			np.random.shuffle(self.signal_data)
			np.random.shuffle(self.background_data)

	def __data_generation(self, index):
		X = self.signal_data[index * self.batch_size : (index + 1) * self.batch_size]
		y = np.ones(self.batch_size)

		X = np.vstack((X, self.background_data[index * self.batch_size : (index + 1) * self.batch_size]))
		y = np.concatenate((y, np.zeros(self.batch_size)))

		p = np.random.permutation(len(X))
		X = X[p]
		y = y[p]

		return X, keras.utils.to_categorical(y, num_classes=self.n_classes)
"""
class DataGeneratorV2(keras.utils.Sequence):

	def __init__(self, 
				 file_ids, input_dir='.', 
				 batch_size=32, 
				 dim=(100,4), 
				 n_classes=2, 
				 shuffle=True):
		self.file_ids = file_ids
		self.input_dir = input_dir
		self.batch_size = batch_size
		self.dim = dim
		self.n_classes = n_classes
		self.shuffle = shuffle

		self.file_ids_used = np.zeros(())

		self.on_epoch_end()

	def on_epoch_end(self):
		self.signal_file_ids = np.arange(len(self.file_ids))
		self.background_file_ids = np.arange(len(self.file_ids))
		if self.shuffle:
			np.random.shuffle(self.signal_file_ids)
			np.random.shuffle(self.background_file_ids)

	def load_data(self):
		for idx in self.file_ids:
			fin = np.load(self.input_dir + '/hist_' + idx + '.root.npz')
			if self.signal_data is None and self.background_data is None:
				self.signal_data = fin['signal']
				self.background_data = fin['background']
			else:
				self.signal_data = np.vstack((self.signal_data, fin['signal']))
				self.background_data = np.vstack((self.background_data, fin['background']))
		self.num_signal = self.signal_data.shape[0]
		self.num_background = self.background_data.shape[0]

		print 'Ay got:'
		print '\t', self.num_signal, 'signal events'
		print '\t', self.num_background, 'background events'
		print 'shapes: signal_data =', self.signal_data.shape
		print '        background_data =', self.background_data.shape

	def __len__(self):
		max_signal_batches = np.floor(self.num_signal / self.batch_size)
		max_background_batches = np.floor(self.num_background / self.batch_size)
		return int(min(max_signal_batches, max_background_batches))

	def __getitem__(self, index):
		return self.__data_generation(index)

	def __data_generation(self, index):
		X = self.signal_data[index * self.batch_size : (index + 1) * self.batch_size]
		y = np.ones(self.batch_size)

		X = np.vstack((X, self.background_data[index * self.batch_size : (index + 1) * self.batch_size]))
		y = np.concatenate((y, np.zeros(self.batch_size)))

		p = np.random.permutation(len(X))
		X = X[p]
		y = y[p]

		return X, keras.utils.to_categorical(y, num_classes=self.n_classes)
"""