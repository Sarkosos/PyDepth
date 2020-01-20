# -*- coding: utf-8 -*-
"""CNN_Depth.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1wPAgKmmtuR-VafmW2S5GfMt-mr3NZeyv
"""

import os
import torch
import torchvision
import torch.utils.data as utils
from torchvision import datasets
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Dataset
from torch.autograd import Variable
import torch.nn as nn
from torch import optim
import torch.nn.functional as F
from torchsummary import summary
import timeit
import random
import matplotlib.pyplot as plt
import numpy as np
from sklearn import preprocessing
from skimage.transform import rescale, resize, downscale_local_mean
import pytorch_ssim
height = int(480/2)
width = int(640/2)

'''Creates Random tensor that is the same size as the image (for testing)'''
def imageBatch(nb_image):
    imgBatch = torch.rand(nb_image, 3, width, height)
    return imgBatch

'''Creates Random tensor that is the same size as the depthmap (for testing)'''
def depthBatch(nb_image):
    depthBatch = torch.rand(nb_image, width*height, 1, 1)
    return depthBatch

def normalize(imageBatch):
    for i in range(len(imageBatch)):
      imageBatch[i] = preprocessing.normalize(imageBatch[i], norm='l2', axis=1, copy=True, return_norm=False)
    return imageBatch

'''CNN doing the first stage of the Semi-Siamese Network (forms the two 'heads')'''
def firstStageCNN():
    return nn.Sequential(nn.Conv2d(3, 32, kernel_size=3, stride=2),  # optional: add stride
                         nn.ReLU(inplace=True),
                         nn.LocalResponseNorm(5, alpha=0.0001, beta=0.75, k=1),

                         nn.Conv2d(32, 62, kernel_size=3, stride=2),
                         nn.ReLU(inplace=True),
                         nn.LocalResponseNorm(5, alpha=0.0001, beta=0.75, k=1),
                         nn.MaxPool2d(kernel_size=3),  # optional: add stride
                         nn.ReLU(inplace=True),

                         nn.Conv2d(62, 92, kernel_size=3, stride=2),  # optional: add stride
                         nn.ReLU(inplace=True),
                         nn.LocalResponseNorm(5, alpha=0.0001, beta=0.75, k=1),

                         nn.MaxPool2d(kernel_size=3),  # optional: add stride
                         nn.ReLU(inplace=True))

'''Form the complete network by taking the two heads and connecting them to
the body'''
class SiameseNetwork(nn.Module):
    def __init__(self):
        super(SiameseNetwork, self).__init__()

        self.cnn1 = firstStageCNN()

        self.cnn2 = firstStageCNN()

        self.fc = nn.Sequential(nn.Conv2d(2208, 92, kernel_size=1),
                                nn.ReLU(inplace=True),

                                nn.Upsample(scale_factor=2, mode='nearest'),
                                nn.ReLU(inplace=True),

                                nn.Conv2d(92, 62, kernel_size=1),
                                nn.ReLU(inplace=True),

                                nn.Upsample(scale_factor=2, mode='nearest'),
                                nn.ReLU(inplace=True),

                                nn.Conv2d(62, 32, kernel_size=4),
                                nn.ReLU(inplace=True),

                                nn.Conv2d(32, width*height, kernel_size=1),
                                nn.ReLU(inplace=True),
                                nn.Softmax2d()
                                )

    '''forwards through the first CNNs to the Main body then returns the output'''
    def forward(self, input1, input2):
        output1 = self.cnn1(input1)
        output2 = self.cnn2(input2)

        combined = torch.cat((output1.view(output1.size(0), -1),
                              output2.view(output2.size(0), -1)), dim=1)

        combined = torch.unsqueeze(combined, 2)
        combined = torch.unsqueeze(combined, 3)
        out = self.fc(combined)
        return out

''' Does the training of the whole dataset'''
def train(net, training_DATA_LEFT, training_DATA_RIGHT, depthMaps, EPOCHS, BATCH_SIZE):
    optimizer = optim.Adam(net.parameters(), lr=0.005)
    loss_function = pytorch_ssim.SSIM(window_size=11)
    dataset = utils.TensorDataset(training_DATA_LEFT, training_DATA_RIGHT, depthMaps)
    train_dataloader = DataLoader(dataset, shuffle=True, num_workers=0, batch_size=1)
    net.zero_grad()
    COUNTER = 1
    avg_loss = []
    print("train function was executed")
    for epoch in range(EPOCHS):
        for i, data in enumerate(train_dataloader):

            img1, img2, depthmap = data
            optimizer.zero_grad() # reset gradient
            outputs = net(img1, img2)
            loss = loss_function(depthmap, outputs)
            print("Loss:", loss)
            avg_loss.append(loss.detach())

            loss.backward()
            optimizer.step()
        #Print out images and epoch numbers 
        print("Epoch number: ", COUNTER)
        COUNTER += 1 
        avg_loss = np.array(avg_loss)
        print("Average Loss:", np.mean(avg_loss))
        avg_loss = []
        plt.figure()
        plt.imshow((outputs.view(height,width)).detach().numpy())
        # plt.show()
        plt.figure()
        plt.imshow((depthmap.view(height,width)).detach().numpy())
        # plt.show
        image = img1.view(3,height,width)
        plt.figure()
        plt.imshow(np.swapaxes(np.swapaxes(image.detach().numpy(),0,2),0,1))
        plt.show()
        outputs = net(img1, img2)
        img1 = img1.view(3,height,width)
        plt.figure()
        plt.imshow((outputs.view(height,width)).detach().numpy())
        plt.figure()
        plt.imshow((depthmap.view(height,width)).detach().numpy())
        plt.figure()
        plt.imshow(np.swapaxes(np.swapaxes(img1.detach().numpy(),0,2),0,1))
        plt.show()
    return net
def rescale_img(imageL, imageR, depthMap):
  resizedL = []
  resizedR = []
  resizedDepth = []
  for img in imageL:
    resizedL.append(rescale(img, (1,0.5,0.5), anti_aliasing=True))
  for img in imageR:
    resizedR.append(rescale(img, (1,0.5,0.5), anti_aliasing=True))
  for img in depthMap:
    resizedDepth.append(rescale(img, 0.5, anti_aliasing=True))
  return np.array(resizedL), np.array(resizedR), np.array(resizedDepth)

def main():
    height = 240
    width = 320
    net = SiameseNetwork()
    #This will import the real dataset in tensor arrays once the data is available
    training_DATA_LEFT = np.load('C:/Users/szymo/Documents/left_images_numpy.npy')
    training_DATA_RIGHT = np.load('C:/Users/szymo/Documents/right_images_numpy.npy')
    depthMaps = np.load('C:/Users/szymo/Documents/depthmaps_numpy.npy')
    training_DATA_LEFT = np.swapaxes(training_DATA_LEFT,1,3)
    training_DATA_RIGHT = np.swapaxes(training_DATA_RIGHT,1,3)
    training_DATA_LEFT, training_DATA_RIGHT, depthMaps = rescale_img(training_DATA_LEFT, training_DATA_RIGHT, depthMaps)
    # depthMaps = normalize(depthMaps)

    training_DATA_LEFT = torch.from_numpy(training_DATA_LEFT)
    training_DATA_RIGHT = torch.from_numpy(training_DATA_RIGHT)
    depthMaps = torch.from_numpy(depthMaps)
    # reshape output
    depthMaps = depthMaps.view(-1,int(width*height),1,1)
    network = final = train(net, training_DATA_LEFT, training_DATA_RIGHT, depthMaps, EPOCHS = 15, BATCH_SIZE = 5)
    torch.save(network, 'saved_network')

if __name__ == '__main__':
    main()

