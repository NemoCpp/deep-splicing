from keras.optimizers import SGD, adam
from keras.models import Sequential, Graph
from keras.layers.core import Dense, Dropout, Activation, Flatten, Merge
from keras.layers.convolutional import Convolution2D, MaxPooling2D
from keras.layers.normalization import BatchNormalization
import cv2
import numpy as np
from tqdm import tqdm
import time
import os
import myfilelib as MY


def VGG_regression_net(data_shape):
    # create a network
    model = Sequential()
    # input: 100x100 images with 3 channels -> (3, 100, 100) tensors.
    # this applies 32 convolution filters of size 3x3 each.
    model.add(Convolution2D(32, 3, 3, border_mode='valid', input_shape=(data_shape[0], data_shape[1], data_shape[2])))
    model.add(Activation('relu'))
    model.add(Convolution2D(32, 3, 3))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(BatchNormalization(epsilon=5e-5, momentum=0.75))
    model.add(Dropout(0.25))

    model.add(Convolution2D(64, 3, 3, border_mode='valid'))
    model.add(Activation('relu'))
    model.add(Convolution2D(64, 3, 3))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(BatchNormalization(epsilon=5e-5, momentum=0.75))
    model.add(Dropout(0.25))

    model.add(Flatten())
    # Note: Keras does automatic shape inference.
    model.add(Dense(256))
    model.add(Activation('relu'))

    model.add(Dense(1))
    model.add(Activation('relu'))
    print ('VGG_regression_net... nb params: {}'.format(model.count_params()))
    return model

def VGG_regression_net_graph(data_shape):
    # create a network
    model = Graph()
    model.add_input(name='data_in', input_shape=(data_shape[0], data_shape[1], data_shape[2]))
    model.add_node(Convolution2D(32, 3, 3, border_mode='valid'), name='conv1', input='data_in')
    model.add_node(Activation('relu'), name='relu1', input='conv1')
    model.add_node(Convolution2D(32, 3, 3), name='conv2', input='relu1')
    model.add_node(Activation('relu'), name='relu2', input='conv2')
    model.add_node(MaxPooling2D(pool_size=(2, 2)), name='pool1', input='relu2')
    # model.add(Dropout(0.25))

    model.add_node(Convolution2D(64, 3, 3, border_mode='valid'), name='conv3', input='pool1')
    model.add_node(Activation('relu'), name='relu3', input='conv3')
    model.add_node(Convolution2D(64, 3, 3), name='conv4', input='relu3')
    model.add_node(Activation('relu'), name='relu4', input='conv4')
    model.add_node(MaxPooling2D(pool_size=(2, 2)), name='pool2', input='relu4')
    # model.add(Dropout(0.25))

    model.add_node(Flatten(), name='flatten', input='pool2')
    model.add_node(Dense(256), name='dense1', input='flatten')
    model.add_node(Activation('relu'), name='relu5', input='dense1')

    model.add_node(Dense(1), name='dense2', input='relu5')
    model.add_node(Activation('relu'), name='reluout', input='dense2')
    model.add_output(name='output', input='reluout')
    print ('VGG_regression_net_graph... nb params: {}'.format(model.count_params()))
    return model


def exhaustive_patch_sampling(image, patch_size = 40, stride = 20):
    (rows, cols, channels) = image.shape
    bias_rows = int(round((rows % patch_size)/2))
    bias_cols = int(round((cols % patch_size)/2))
    patch_list = []
    for r in range(bias_rows, rows - bias_rows - patch_size, stride):
        for c in range(bias_cols, cols - bias_cols - patch_size, stride):
            patch = image[r:r+patch_size, c:c+patch_size, :]
            patch_list.append(patch)
    # now list containing image as (rows, cols, channels)
    # need to be exported as a ndarray (n_samples, n_channels, n_rows, n_cols)
    nb_patches = len(patch_list)
    parray = np.zeros((nb_patches, 3, patch_size, patch_size))
    for i in range(nb_patches):
        img = patch_list[i]
        new_img = np.rollaxis(img, 2, 0)
        parray[i, :, :, :] = new_img
    return parray

def get_patch_array(myimages, description):
    for i in tqdm(range(len(myimages)), desc=description):
        # Load an color image in BGR
        img = cv2.imread(myimages[i].image_path, flags=cv2.IMREAD_COLOR)
        tmp_plist = exhaustive_patch_sampling(img, patch_size=40, stride=20)
        nb_samples = int(tmp_plist.shape[0])
        if myimages[i].label == 0:
            tmp_labels = np.zeros((nb_samples, 1))
        elif myimages[i].label == 1:
            tmp_labels = np.ones((nb_samples, 1))
        else:
            raise ("A label different fro 0 and 1 is not possible.")
        # Creation of the training set
        if i == 0:
            x = tmp_plist
            y = tmp_labels
        else:
            x = np.concatenate((x, tmp_plist))
            y = np.concatenate((y, tmp_labels))
    return x, y

def run_cnn(training_images, test_images, settings):
    nb_training = len(training_images)
    nb_test = len(test_images)

    # extract patches for training
    t0 = time.time()
    train_x, train_y = get_patch_array(training_images, 'Creation of training set')

    # extract patches for test
    t1 = time.time()
    test_x, test_y = get_patch_array(test_images, 'Creation of test set') # Non necessario se non per validation

    # Create Model
    t2 = time.time()
    model = VGG_regression_net_graph((train_x.shape[1], train_x.shape[2], train_x.shape[3]))
    model.compile(loss='categorical_crossentropy', optimizer='Adam')
    nb_params = model.count_params()

    # Train model
    t3 = time.time()
    modelfileweights = os.path.join(settings.working_folder, 'modelNN_weights_ep{0:02d}_bs{1:02d}.h5'.format(settings.nb_epochs, settings.batch_size))
    modelfilename = os.path.join(settings.working_folder, 'modelNN_ep{0:02d}_bs{1:02d}.json'.format(settings.nb_epochs, settings.batch_size))
    model.fit((train_x, train_y), batch_size=settings.batch_size, nb_epoch=settings.nb_epochs, validation_data=(test_x, test_y))

    # Save the model
    t4 = time.time()
    json_string = model.to_json()
    open(modelfilename, 'w').write(json_string)
    model.save_weights(modelfileweights, overwrite=True)

    ###### Test model #####
    t5 = time.time()
    results = np.zeros((nb_test, 1))
    for i in range(nb_test):
        img = cv2.imread(test_images[i].image_path, flags=cv2.IMREAD_COLOR)
        test_x = exhaustive_patch_sampling(img, patch_size=40, stride=20)
        nb_extracted_patches = len(test_x)
        prediction = model.predict_classes(test_x, batch_size=settings.batch_size, verbose=True)
        nb_0 = len(prediction.argwhere(0))
        nb_1 = len(prediction.argwhere(1))
        if nb_0 > nb_1:
            pred = 0
        else:
            pred = 1
        results[i, 0] = pred

    t6 = time.time()
    print('Time get training samples: {}'.format(MY.hms_string(t1 - t0)))
    print('Time get test samples: {}'.format(MY.hms_string(t2 - t1)))
    print('Time to generate the model: {}'.format(MY.hms_string(t3 - t2)))
    print('Time for training the model: {}'.format(MY.hms_string(t4 - t3)))
    print('Time for saving the model: {}'.format(MY.hms_string(t5 - t4)))
    print('Time for testing model: {}'.format(MY.hms_string(t6 - t5)))
    return results
