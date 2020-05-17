import numpy as np
from keras.layers import Input, Dense, Reshape, Flatten, Dropout, Embedding, Concatenate
from keras.layers import BatchNormalization, Activation, ZeroPadding2D
from keras.layers.advanced_activations import LeakyReLU
from keras.layers.convolutional import UpSampling2D, Conv2D, Conv2DTranspose
from keras.models import Model
from keras.optimizers import Adam
from keras.initializers import RandomNormal
import matplotlib.pyplot as plt
import numpy as np
import numpy.random
from numpy.random import choice
from numpy.random import randn

#import data
dataDir = '/home/MilliQan/data/disappearingTracks/tracks/'
workDir = '/home/llavezzo/'
plotDir = workDir + 'images/acgan/'
weightsDir = workDir + 'weights/acgan/'

#workDir = 'c:/users/llave/Documents/CMS/'
data_match = np.load(workDir+'images_DYJets50_GEN_RECO_match.npy')
data_no_match = np.load(workDir+'images_DYJets50_GEN_RECO_no_match.npy')
classes = np.concatenate([np.ones(len(data_match)),np.zeros(len(data_no_match))])
data = np.concatenate([data_match,data_no_match])
print(data_match.shape,data_no_match.shape,data.shape)
print(len(classes))

#shuffle
indices = np.arange(data.shape[0])
np.random.shuffle(indices)
data = data[indices]
classes = classes[indices]

def build_discriminator(img_shape,n_classes=2):
    input = Input(img_shape)
    x = Conv2D(32*3, kernel_size=(4,4), strides=(2,2), padding="same")(input)
    x = LeakyReLU(alpha=0.2)(x)
    x = Dropout(0.25)(x)
    x = Conv2D(64*3, kernel_size=(4,4), strides=(2,2), padding="same")(x)
    x = ZeroPadding2D(padding=((0, 1), (0, 1)))(x)
    x = (LeakyReLU(alpha=0.2))(x)
    x = Dropout(0.25)(x)
    x = BatchNormalization(momentum=0.8)(x)
    x = Conv2D(128*3, kernel_size=(4,4), strides=(2,2), padding="same")(x)
    x = LeakyReLU(alpha=0.2)(x)
    x = Dropout(0.25)(x)
    x = BatchNormalization(momentum=0.8)(x)
    x = Conv2D(256*3, kernel_size=(4,4), strides=(1,1), padding="same")(x)
    x = LeakyReLU(alpha=0.2)(x)
    x = Dropout(0.25)(x)
    x = Flatten()(x)
    # real/fake output
    out1 = Dense(1, activation='sigmoid')(x)
    # class label output
    out2 = Dense(n_classes, activation='softmax')(x)

    model = Model(input, [out1, out2])
    print("-- Discriminator -- ")
    model.summary()
    
    model.compile(loss=['binary_crossentropy', 'sparse_categorical_crossentropy'], optimizer=Adam(lr=0.0002, beta_1=0.5))
    return model

# define the standalone generator model
def build_generator(latent_dim, n_classes=2):
    # weight initialization
    init = RandomNormal(stddev=0.02)
    # label input
    in_label = Input(shape=(1,))
    # embedding for categorical input
    li = Embedding(n_classes, 50)(in_label)
    # linear multiplication
    n_nodes = 10 * 10
    li = Dense(n_nodes, kernel_initializer=init)(li)
    # reshape to additional channel
    li = Reshape((10, 10, 1))(li)
    # image generator input
    in_lat = Input(shape=(latent_dim,))
    # foundation for 10x10 image
    n_nodes = 384 * 10 * 10
    gen = Dense(n_nodes, kernel_initializer=init)(in_lat)
    gen = Activation('relu')(gen)
    gen = Reshape((10, 10, 384))(gen)
    # merge image gen and label input
    merge = Concatenate()([gen, li])
    # upsample to 20x20
    gen = Conv2DTranspose(192, (5,5), strides=(2,2), padding='same', kernel_initializer=init)(merge)
    gen = BatchNormalization()(gen)
    gen = Activation('relu')(gen)
    # upsample to 40x40
    gen = Conv2DTranspose(3, (5,5), strides=(2,2), padding='same', kernel_initializer=init)(gen)
    out_layer = Activation('tanh')(gen)
    # define model
    model = Model([in_lat, in_label], out_layer)
    print("-- Generator -- ")
    model.summary()
    return model

#plots events
def plot_event(eventNum):
    
    x = events[eventNum]
    
    fig, axs = plt.subplots(1,3)
    for i in range(3):
        axs[i].imshow(x[:,:,i])
        
    axs[0].set_title("ECAL")
    axs[1].set_title("HCAL")
    axs[2].set_title("Muon")
    
    plt.show()

#generates and saves 5 random images
def save_imgs(generator, epoch, batch):
    r, c = 5, 3
    noise = np.random.normal(0, 1, (r * c, 100))
    gen_imgs = generator.predict(noise)

    # Rescale images 0 - 1
    gen_imgs = 0.5 * gen_imgs + 0.5

    fig, axs = plt.subplots(r, c)
    cnt = 0
    for i in range(r):
        for j in range(c):
            axs[i, j].imshow(gen_imgs[cnt, :, :, j], cmap='gray')
            axs[i, j].axis('off')
            cnt += 1
    fig.savefig(plotDir + ac_gan_%d_%d.png" % (epoch, batch))
    plt.close()
    
# define the combined generator and discriminator model, for updating the generator
def build_gan(g_model, d_model):
    # make weights in the discriminator not trainable
    d_model.trainable = False
    # connect the outputs of the generator to the inputs of the discriminator
    gan_output = d_model(g_model.output)
    # define gan model as taking noise and label and outputting real/fake and label outputs
    model = Model(g_model.input, gan_output)
    # compile model
    model.compile(loss=['binary_crossentropy', 'sparse_categorical_crossentropy'], optimizer=Adam(lr=0.0002, beta_1=0.5))
    print("-- GAN -- ")
    model.summary()
    return model
    
# size of the latent space
latent_dim = 100
# create the discriminator
discriminator = build_discriminator(img_shape=(40,40, 3),n_classes=2)
# create the generator
generator = build_generator(latent_dim)
# create the gan
gan_model = build_gan(generator, discriminator)

def noisy_labels(y, p_flip):
    # determine the number of labels to flip
    n_select = int(p_flip * y.shape[0])
    # choose labels to flip
    flip_ix = choice([i for i in range(y.shape[0])], size=n_select)
    # invert the labels in place
    y[flip_ix] = 1 - y[flip_ix]
    return y

# generate points in latent space as input for the generator
def generate_latent_points(latent_dim, n_samples):
    # generate points in the latent space
    x_input = randn(latent_dim * n_samples)
    # reshape into a batch of inputs for the network
    x_input = x_input.reshape((n_samples, latent_dim))
    return x_input

def smooth_positive_labels(y):
    return y - 0.3 + (np.random.random(y.shape) * 0.5)

def smooth_negative_labels(y):
    return y + np.random.random(y.shape) * 0.3

X_train = data
y_train = classes

epochs=100
batch_size=16
save_interval=1

num_examples = X_train.shape[0]
num_batches = int(num_examples / float(batch_size))
print('Number of examples: ', num_examples)
print('Number of Batches: ', num_batches)
print('Number of epochs: ', epochs)

half_batch = int(batch_size / 2)

d_loss_array = []
g_loss_array = []

for epoch in range(epochs + 1):
    for batch in range(num_batches):

        # noise images for the batch
        noise = generate_latent_points(100,half_batch)
        fake_classes = np.random.randint(0,2,size=half_batch)
        fake_images = generator.predict([noise,fake_classes])
        fake_labels = np.zeros((half_batch, 1))

        # real images for batch
        idx = np.random.randint(0, X_train.shape[0], half_batch)
        real_images = X_train[idx]
        real_classes = y_train[idx]
        real_labels = np.ones((half_batch, 1))
        
        #noisy labels
        real_labels = noisy_labels(real_labels,0.05)
        real_labels = smooth_positive_labels(real_labels)
        fake_labels = smooth_negative_labels(fake_labels)

        # Train the discriminator (real classified as 1 and generated as 0)
        d_loss_real = discriminator.train_on_batch(real_images, [real_classes,real_labels])
        d_loss_fake = discriminator.train_on_batch(fake_images, [fake_classes,fake_labels])

        # Train the generator
        labels = np.ones((batch_size, 1))
        classes = np.random.randint(0, 2, batch_size)
        noise = generate_latent_points(100,batch_size)
        
        g_loss = gan_model.train_on_batch([noise,classes], [labels,classes])

        
        # Track the progress
        if(batch % 50 == 0): 
            print('epoch %d batch %d, dr[%.3f,%.3f], df[%.3f,%.3f], g[%.3f,%.3f]' % 
              (epoch, batch, d_loss_real[1],d_loss_real[1], 
               d_loss_fake[1],d_loss_fake[2], g_loss[1],g_loss[2]))

    
    
    save_imgs(generator, epoch, batch)
    gan_model.save_weights(weightsDir+'G_epoch{0}.h5'.format(epoch))
    discriminator.save_weights(weightsDir+'D_epoch{0}.h5'.format(epoch))