import os
import keras
import numpy as np
import random
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from keras.models import Sequential
from keras.layers import Dense, Dropout, Flatten, Conv2D, MaxPooling2D, BatchNormalization
from keras import callbacks
from keras import backend as K
from keras.preprocessing.image import ImageDataGenerator
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from collections import Counter
from utils import *

dataDir = '/data/disappearingTracks/tracks/'
workDir = '/home/llavezzo/'
plotDir = workDir + 'plots/cnn_aug2/'
weightsDir = workDir + 'weights/cnn_aug2/'

os.system('mkdir '+str(plotDir))
os.system('mkdir '+str(weightsDir))

#config parameters
num_classes = 2
epochs = 100
batch_size = 16
patienceCount = 10  

# input image dimensions
img_rows, img_cols = 40, 40
channels = 3
input_shape = (img_rows,img_cols,channels)

# load the data, split between train and test sets
data_e = np.load(dataDir+'e_DYJets50_v4_norm_40x40.npy')
data_bkg = np.load(dataDir+'bkg_DYJets50_v4_norm_40x40.npy')
e_reco_results = np.load(dataDir + 'e_reco_DYJets50_v4_norm_40x40.npy')
bkg_reco_results = np.load(dataDir + 'bkg_reco_DYJets50_v4_norm_40x40.npy')
classes = np.concatenate([np.ones(len(data_e)),np.zeros(len(data_bkg))])
data = np.concatenate([data_e,data_bkg])
data = data[:,:,:,[1,3,4]]
reco_results = np.concatenate([e_reco_results,bkg_reco_results])

# split real data only
x_train, x_test, y_train, y_test, reco_train, reco_test = train_test_split(data, classes, reco_results, test_size=0.30, random_state=42)

x_train = x_train.astype('float32')
x_test = x_test.astype('float32')
y_train = y_train.astype('int64')
y_test = y_test.astype('int64')
print('x_train shape:', x_train.shape)
print(x_train.shape[0], 'train samples')
print(x_test.shape[0], 'test samples')

# Image augmentation
train_datagen = ImageDataGenerator(
    # samplewise_center = True,              #FIXME: try samplewise
    # samplewise_std_normalization = True,
    width_shift_range = 0.2,
    height_shift_range = 0.2,
    # brightness_range = [0.8,1.2]
    horizontal_flip = True,
    fill_mode = 'nearest'
)   

train_datagen.fit(x_train)

y_train = keras.utils.to_categorical(y_train, num_classes)
y_test = keras.utils.to_categorical(y_test, num_classes)

model = Sequential()
model.add(Conv2D(32, kernel_size=(3, 3),
                 activation='relu',
                 input_shape=input_shape))
model.add(MaxPooling2D(pool_size=(2, 2)))
model.add(BatchNormalization()) # testing
model.add(Conv2D(64, (3, 3), activation='relu'))
model.add(MaxPooling2D(pool_size=(2, 2)))
model.add(BatchNormalization()) # testing
model.add(Flatten())
model.add(Dense(128, activation='relu'))
model.add(Dropout(0.5))
model.add(Dense(num_classes, activation='softmax'))

model.compile(loss=keras.losses.categorical_crossentropy,
              optimizer=keras.optimizers.Adadelta(),
              metrics=['accuracy'])

callbacks = [
    callbacks.EarlyStopping(monitor='val_loss',patience=patienceCount),
    callbacks.ModelCheckpoint(filepath=weightsDir+'best_model.{epoch:02d}.h5',save_best_only=True),
]

history = model.fit(train_datagen.flow(x_train,y_train,batch_size=batch_size),
          steps_per_epoch = len(x_train) // batch_size,
          epochs=epochs,
          verbose=2,
          validation_data=(x_test,y_test),
          callbacks=callbacks)

model.save_weights(weightsDir + 'first_aug_model.h5')

plt.plot(history.history['accuracy'],label='train')
plt.plot(history.history['val_accuracy'],label='test')
plt.legend()
plt.savefig(plotDir+'accuracy_history.png')
plt.clf()
plt.plot(history.history['loss'],label='train')
plt.plot(history.history['val_loss'],label='test')
plt.legend()
plt.savefig(plotDir+'loss_history.png')
plt.clf()

predictions = model.predict(x_test)

print()
print("Calculating and plotting confusion matrix")
cm = calc_cm(y_test,predictions)
plot_confusion_matrix(cm,['bkg','e'],plotDir + 'cm.png')
print()

print("Plotting ceratainty")
plot_certainty(y_test,predictions,plotDir+'certainty.png')
print()

precision, recall = calc_binary_metrics(cm)
print("Precision = TP/(TP+FP) = fraction of predicted true actually true ",precision)
print("Recall = TP/(TP+FN) = fraction of true class predicted to be true ",recall)
auc = roc_auc_score(y_test,predictions)
print("AUC Score:",auc)
print()

m = np.zeros([2,2,2])
for true,pred,reco in zip(y_test, predictions, reco_test):
    t = np.argmax(true)
    p = np.argmax(pred)
    m[t][p][reco] += 1
    
label = ['bkg','e']
print("Pred:\t\t\t bkg\t\t\t e")
for i in range(2):
    print("True: ",label[i],end="")
    for j in range(2):
        print("\t\t",int(m[i][j][0]),"\t",int(m[i][j][1]),end="")
    print()
print()