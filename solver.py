from __future__ import print_function
from __future__ import division
import torch
import torchvision
from torchvision import datasets, transforms, models
import torch.nn as nn
import torch.optim as optim

import numpy as np
import pandas as pd 
import matplotlib.pyplot as plt 
import pandas as pd 

import copy
import time

from CelebA import get_loader
import torch.nn.functional as F
# from tensorboardX import SummaryWriter
from FaceAttr_baseline_model import FaceAttrModel

import focal_loss.focal_loss as focal_loss

import config as cfg

class Solver(object):
    
    def __init__(self):

        self.epoches = cfg.epoches 
        self.batch_size = cfg.batch_size
        self.learning_rate = cfg.learning_rate
        self.selected_attrs = cfg.selected_attrs
        self.momentum = cfg.momentum
        self.device = torch.device("cuda:" + str(cfg.DEVICE_ID) if torch.cuda.is_available() else "cpu")
        self.image_dir = cfg.image_dir
        self.attr_path = cfg.attr_path
        self.pretrained = cfg.pretrained
        self.model_type = cfg.model_type
        self.build_model(cfg.model_type, cfg.pretrained)
        self.create_optim(cfg.optim_type)
        self.train_loader = None
        self.validate_loader = None
        self.log_dir = cfg.log_dir
        self.use_tensorboard = cfg.use_tensorboard
        self.attr_loss_weight = torch.tensor(cfg.attr_loss_weight).to(self.device)
        self.attr_threshold = cfg.attr_threshold
        self.model_save_path = cfg.exp_version + '-Resnet101' + '-best_model.pth'  # default
        self.LOADED = False
        

    def build_model(self, model_type, pretrained):
        """Here should change the model's structure""" 
        self.model = FaceAttrModel(model_type, pretrained, self.selected_attrs).to(self.device)


    def build_tensorboard(self):
        """Build a tensorboard logger."""
        from logger import Logger
        self.logger = Logger(self.log_dir)


    def create_optim(self, optim_type):
        if optim_type == "Adam":
            self.optim = optim.Adam(self.model.parameters(), lr = self.learning_rate)
        elif optim_type == "SGD":
            self.optim = optim.SGD(self.model.parameters(), lr = self.learning_rate, momentum = self.momentum)


    def print_network(self, model, name):
        """Print out the network information."""
        num_params = 0
        for p in model.parameters():
            num_params += p.numel()
        print(model)
        print(name)
        print("The number of parameters: {}".format(num_params))


    def set_transform(self, mode):
        transform = []
        if mode == 'train':
            transform.append(transforms.RandomHorizontalFlip())
        # the advising transforms way in imagenet
        # the input image should be resized as 224 * 224 for resnet.
        transform.append(transforms.Resize(size=(224, 224)))
        transform.append(transforms.ToTensor())
        transform.append(transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]))
        transform = transforms.Compose(transform)
        self.transform = transform

    
    # show curve of loss or accuracy
    def show_curve(self, ys, title):
        x = np.array([i for i in range(len(ys))])
        y = np.array(ys)
        plt.figure()
        plt.plot(x, y, c='b')
        plt.axis()
        plt.title('{} curve'.format(title))
        plt.xlabel('epoch')
        plt.ylabel('{} value'.format(title))
        plt.show()
        plt.savefig("{}.jpg".format(title))

    # self define loss function
    def BCE_loss(self, input_, target):
        # cost_matrix = [1 for i in range(len(self.selected_attrs))]
        total_loss = torch.tensor([0.0]).to(self.device)
        for i in range(self.batch_size):
            attr_list = []
            for j, attr in enumerate(self.selected_attrs):
                attr_list.append(target[j][i])
            attr_tensor = torch.tensor(attr_list)
            """
            loss = F.binary_cross_entropy_with_logits(input_[i].to(self.device),  
                                                    attr_tensor.type(torch.FloatTensor).to(self.device), 
                                                    weight=self.attr_loss_weight.type(torch.FloatTensor).to(self.device)) 
            """
            loss = F.binary_cross_entropy(input_[i].to(self.device),  
                                          attr_tensor.type(torch.FloatTensor).to(self.device), 
                                          weight=self.attr_loss_weight.type(torch.FloatTensor).to(self.device))
            total_loss += loss
        return total_loss


    def train(self, epoch):
        """
        Return: the average trainging loss value of this epoch
        """
        self.model.train()
        self.set_transform("train")

        # to avoid loading dataset repeatedly
        if self.train_loader == None:
            self.train_loader = get_loader(image_dir = self.image_dir, attr_path = self.attr_path, 
        selected_attrs = self.selected_attrs, mode="train", batch_size=self.batch_size, transform=self.transform)
            print("train_dataset: {}".format(len(self.train_loader.dataset)))

        temp_loss = 0.0
        
        
        focal_loss_func = None
        if cfg.loss_type == "focal_loss":
            focal_loss_func = focal_loss().to(self.device)
            
        # loss_log = {}
        # start to train in 1 epoch
        # print(self.train_loader)
        for batch_idx, samples in enumerate(self.train_loader):
            print("training batch_idx : {}".format(batch_idx))
            images, labels = samples["image"], samples["label"]
            #print(images, labels)
            images= images.to(self.device)
            outputs = self.model(images)
            self.optim.zero_grad()
            
            #total_loss = self.criterion(outputs[0], labels)
            if cfg.loss_type == "BCE_loss":
                total_loss = self.BCE_loss(outputs, labels)
            elif cfg.loss_type == "focal_loss":
                total_loss = focal_loss_func(outputs, labels)

            total_loss.backward()

            self.optim.step()
            temp_loss += total_loss.item()
            
        # log the training info 
        """
        for attr in self.selected_attrs:
            loss_log[attr] /= batch_idx + 1
        if self.use_tensorboard:
            for tag, value in loss_log.items():
                self.logger.scalar_summary(tag, value, epoch+1)   
        """
        return temp_loss/(batch_idx + 1)
        
    def evaluate(self, mode):
        """
        Mode: validate or test mode
        Return: correct_dict: save the average predicting accuracy of every attribute
        """
        
        self.model.eval()

        self.set_transform(mode)
        if self.validate_loader == None:
            self.validate_loader = get_loader(image_dir = self.image_dir, 
                                    attr_path = self.attr_path, 
                                    selected_attrs = self.selected_attrs,
                                    mode=mode, batch_size=self.batch_size, transform=self.transform)
            print("{}_dataset: {}".format(mode,len(self.validate_loader.dataset)))
        
        correct_dict = {}
        for attr in self.selected_attrs:
            correct_dict[attr] = 0

        confusion_matrix_dict = {}
        confusion_matrix_dict['TP'] = [0 for i in range(len(self.selected_attrs))]
        confusion_matrix_dict['TN'] = [0 for i in range(len(self.selected_attrs))]
        confusion_matrix_dict['FP'] = [0 for i in range(len(self.selected_attrs))]
        confusion_matrix_dict['FN'] = [0 for i in range(len(self.selected_attrs))]
        confusion_matrix_dict['precision'] = [0 for i in range(len(self.selected_attrs))]
        confusion_matrix_dict['recall'] = [0 for i in range(len(self.selected_attrs))]
        confusion_matrix_dict['TPR'] = [0 for i in range(len(self.selected_attrs))]
        confusion_matrix_dict['FPR'] = [0 for i in range(len(self.selected_attrs))]
        confusion_matrix_dict['F1'] = [0 for i in range(len(self.selected_attrs))]

        with torch.no_grad():
            for batch_idx, samples in enumerate(self.validate_loader):
                images, labels = samples["image"], samples["label"]
                images = images.to(self.device)
                outputs = self.model(images)

                # get the accuracys of the current batch
                for i in range(self.batch_size):
                    for j, attr in enumerate(self.selected_attrs):
                        pred = outputs[i].data[j]
                        pred = 1 if pred > self.attr_threshold[j] else 0

                        # record accuracy
                        if pred == labels[j][i]:
                            correct_dict[attr] = correct_dict[attr] + 1

                        if pred == 1 and labels[j][i] == 1:
                            confusion_matrix_dict['TP'][j] += 1
                        if pred == 1 and labels[j][i] == 0:
                            confusion_matrix_dict['FP'][j] += 1
                        if pred == 0 and labels[j][i] == 1:
                            confusion_matrix_dict['TN'][j] += 1
                        if pred == 0 and labels[j][i] == 0:
                            confusion_matrix_dict['FN'][j] += 1

            i = 0
            # get the average accuracy
            for attr in self.selected_attrs:
                correct_dict[attr] = correct_dict[attr] * 100 / len(self.validate_loader.dataset)
                confusion_matrix_dict['precision'][i] = confusion_matrix_dict['TP'][i]/(confusion_matrix_dict['FP'][i] 
                                                        + confusion_matrix_dict['TP'][i])
                confusion_matrix_dict['recall'][i]= confusion_matrix_dict['TP'][i]/(confusion_matrix_dict['FN'][i] 
                                                    + confusion_matrix_dict['TP'][i])
                confusion_matrix_dict['TPR'][i]= confusion_matrix_dict['TP'][i]/(confusion_matrix_dict['TP'][i] 
                                                    + confusion_matrix_dict['FN'][i])
                confusion_matrix_dict['FPR'][i]= confusion_matrix_dict['FP'][i]/(confusion_matrix_dict['FP'][i] 
                                                    + confusion_matrix_dict['TN'][i])
                confusion_matrix_dict['F1'][i] = 2*confusion_matrix_dict['precision']*confusion_matrix_dict['recall']/(confusion_matrix_dict['precision'] + confusion_matrix_dict['recall'])                                                                          
                i += 1

        return correct_dict, confusion_matrix_dict

    def fit(self):
        """
        This function is to combine the train and evaluate, finally getting a best model.
        """
        train_losses = []
      
        best_model_wts = copy.deepcopy(self.model.state_dict())
        best_acc = 0.0
        
        eval_acc_dict = {}
        confusion_matrix_df = None 

        for attr in self.selected_attrs:
            eval_acc_dict[attr] = []

        for epoch in range(self.epoches):
            running_loss = self.train(epoch)
            print("{}/{} Epoch:  in training process，average loss: {:.4f}".format(epoch + 1, self.epoches, running_loss))
            average_acc_dict, confusion_matrix_dict = self.evaluate("validate")
            print("{}/{} Epoch: in evaluating process，average accuracy:{}".format(epoch + 1, self.epoches, average_acc_dict))
            train_losses.append(running_loss)
            average_acc = 0.0

            # Record the evaluating accuracy of every attribute at current epoch
            for attr in self.selected_attrs:
                eval_acc_dict[attr].append(average_acc_dict[attr])
                average_acc += average_acc_dict[attr]
            average_acc /= len(self.selected_attrs) # overall accuracy
            
            # find a better model, save it 
            if average_acc > best_acc: 
                best_acc = average_acc
                best_model_wts = copy.deepcopy(self.model.state_dict())
                confusion_matrix_df = pd.DataFrame(confusion_matrix_dict, index=self.selected_attrs)


        # save the accuracy in files
        timestamp = str(int(time.time()))
        eval_acc_csv = pd.DataFrame(eval_acc_dict, index = [i for i in range(self.epoches)]).T 
        eval_acc_csv.to_csv("./model/" + cfg.exp_version + '-' +  self.model_type + "-eval_accuracy"+ ".csv");

        # save the loss files
        train_losses_csv = pd.DataFrame(train_losses)
        train_losses_csv.to_csv("./model/" + cfg.exp_version + '-' +  self.model_type + "-losses" +".csv")

        # load best model weights
        self.model_save_path = "./model/" + cfg.exp_version + '-' +  self.model_type + "-best_model" + ".pth"
        self.model.load_state_dict(best_model_wts)
        self.LOADED = True
        torch.save(best_model_wts, self.model_save_path)

        # save the confusion matrix of each attributes.
        confusion_matrix_df.to_csv("./model/" + cfg.exp_version + '-' +  self.model_type + '-confusion_matrix' + '.csv', index=self.selected_attrs)

        # test the model with test dataset.
        test_acc_dict, confusion_matrix_dict = self.evaluate("test")
        test_acc_csv = pd.DataFrame(test_acc_dict)
        test_acc_csv.to_csv("./mode/" + cfg.exp_version + '-' + self.model_type + "-test_accuracy" + '.csv')
        test_confusion_matrix_csv = pd.DataFrame(confusion_matrix_dict, index=self.selected_attrs)
        test_confusion_matrix_csv.to_csv("./model/" + cfg.exp_version + '-' + self.model_type + '-confusion_matrix.csv', index=self.selected_attrs)

    def predict(self, image):
        if not self.LOADED:
            # load the best model dict.
            self.model.load_state_dict(torch.load("./" + self.model_save_path))
            self.LOADED = True

        self.model.eval()
        with torch.no_grad():
            self.set_transform("predict")
            output = self.model(self.transform(image))
            pred_dict = {}
            for i, attr in enumerate(self.selected_attrs):
                pred = output.data[i]
                pred = pred if pred > self.attr_threshold[i] else 0
                if pred != 0:
                    pred_dict[attr] = pred
            return pred_dict  # return the predicted positive attributes dict and the probability.
