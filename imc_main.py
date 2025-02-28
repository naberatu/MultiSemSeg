# Environment imports
import sys

import torch
import torchsummary
from torch.utils.data import DataLoader
from torchvision import transforms as transforms
import torch.optim as optim
import os
import random
import warnings
import math

# Image Classifier Utils
from imc_fit import *
from imc_plot_run import *
from imc_dataset import CTDataset
from imc_prune import prune_model
from imc_prune import quantize_model
from torchsummary import summary

# Imported models
from imc_nabernet import NaberNet
from torchvision.models import resnet18
from torchvision.models import resnet50
from torchvision.models import vgg16

# Directories
dir_models = 'C:/Users/elite/PycharmProjects/Pytorch/imc_models/'
dir_models_old = 'C:/Users/elite/PycharmProjects/Pytorch/models_old/'
dir_models_p = 'C:/Users/elite/PycharmProjects/Pytorch/imc_models/pruned/'
dir_models_q = 'C:/Users/elite/PycharmProjects/Pytorch/imc_models/quantized/'
dir_models_pq = 'C:/Users/elite/PycharmProjects/Pytorch/imc_models/pruned_quantized/'
cut_dir = 'C:/Users/elite/PycharmProjects/Pytorch'
dir_orig = 'C:/Users/elite/PycharmProjects/Pytorch/data/covct/'
dir_ctx = 'C:/Users/elite/PycharmProjects/Pytorch/data/ct_ctx/'

warnings.filterwarnings("ignore")
random.seed(12)

# =============================================================
# SELECT: Model, Name, and test_only
# =============================================================
# model_name = "resnet18_bn"
# model = resnet18(pretrained=False)
# model_name = "resnet50_an"
# model = resnet50(pretrained=False)
# model_name = "vgg16_bn"
# model = vgg16(pretrained=False)
model_name = "nabernet_an"
model = NaberNet(0)

# Whether the main should just run a test, or do a full fit.
# params = [True, True, False, False]         # Training
# params = [False, True, False, False]        # Testing
# params = [False, False, True, False]        # Pruning
# params = [False, False, False, True]        # Quantizing
params = [False, False, True, True]         # Pruning & Quantizing
training, graph, prune, quant = params[0], params[1], params[2], params[3]
batchsize = 8       # Chosen for the GPU: RTX 2060

# Loading a pretrained model
if not training:
    model = torch.load(dir_models + model_name + ".pth")
    # model = torch.load(dir_models_old + model_name + ".tar")
    # model_name += '_bpq'

# =============================================================
# SELECT: Dataset Name
# =============================================================
if '_a' in model_name:
    SET_NAME = "UCSD AI4H"              # Contains 746 images.        (Set A)
elif '_b' in model_name:
    SET_NAME = "SARS-COV-2 CT-SCAN"     # Contains 2,481 images.      (Set B)
elif '_c' in model_name:
    SET_NAME = "COVIDx CT-1"            # Contains 115,837 images.    (Set C)

if "naber" in model_name and training and 'ucsd' not in SET_NAME.lower():
    model = NaberNet(1 if 'sars' in SET_NAME.lower() else 2)

# =============================================================
# SELECT: Optimizer and learning rate.
# =============================================================
learning_rate = 0.001
optimizer = optim.Adam(model.parameters(), lr=learning_rate)

# =============================================================
# STEP: Generate Dataset Parameters
# =============================================================
if "ucsd" in SET_NAME.lower():
    CLASSES = ['UCSD_NC', 'UCSD_CO']
    IMGSIZE = 256
    EPOCHS = 10
    normalize = transforms.Normalize(mean=0.6292, std=0.3024)
elif "sars" in SET_NAME.lower():
    CLASSES = ['SARSCT_NC', 'SARSCT_CO']
    IMGSIZE = 256
    EPOCHS = 20
    normalize = transforms.Normalize(mean=0.611, std=0.273)
elif "covidx" in SET_NAME.lower():
    CLASSES = ['CTX_NC', 'CTX_CO']
    IMGSIZE = 256
    EPOCHS = 10
    normalize = transforms.Normalize(mean=0.611, std=0.273)

# print(summary(model=model, input_size=(3, IMGSIZE, IMGSIZE), device='cuda'))
# sys.exit(0)

# =============================================================
# STEP: Setup Dataset Transforms
# =============================================================
train_transformer = transforms.Compose([
    transforms.Resize(IMGSIZE),
    transforms.RandomResizedCrop(IMGSIZE, scale=(0.5, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    normalize
])
val_transformer = transforms.Compose([
    transforms.Resize((IMGSIZE, IMGSIZE)),
    transforms.ToTensor(),
    normalize
])

# =============================================================
# STEP: GENERATE DATASETS
# =============================================================
if "UCSD" in SET_NAME:
    trainset = CTDataset(root_dir=dir_orig,
                         classes=CLASSES,
                         covid_files=dir_orig + 'Data-split/COVID/old_split/trainCT_COVID.txt',
                         non_covid_files=dir_orig + 'Data-split/NonCOVID/old_split/trainCT_NonCOVID.txt',
                         transform=train_transformer)
    valset = CTDataset(root_dir=dir_orig,
                       classes=CLASSES,
                       covid_files=dir_orig + 'Data-split/COVID/old_split/valCT_COVID.txt',
                       non_covid_files=dir_orig + 'Data-split/NonCOVID/old_split/valCT_NonCOVID.txt',
                       transform=val_transformer)
    testset = CTDataset(root_dir=dir_orig,
                        classes=CLASSES,
                        covid_files=dir_orig + 'Data-split/COVID/old_split/testCT_COVID.txt',
                        non_covid_files=dir_orig + 'Data-split/NonCOVID/old_split/testCT_NonCOVID.txt',
                        transform=val_transformer)
elif "SARS" in SET_NAME:
    trainset = CTDataset(root_dir=dir_orig,
                         classes=CLASSES,
                         covid_files=dir_orig + 'Data-split/COVID/sarsct_co_train.txt',
                         non_covid_files=dir_orig + 'Data-split/NonCOVID/sarsct_nc_train.txt',
                         transform=train_transformer)
    testset = CTDataset(root_dir=dir_orig,
                        classes=CLASSES,
                        covid_files=dir_orig + 'Data-split/COVID/sarsct_co_test.txt',
                        non_covid_files=dir_orig + 'Data-split/NonCOVID/sarsct_nc_test.txt',
                        transform=val_transformer)
elif "COVIDx" in SET_NAME:
    trainset = CTDataset(root_dir=dir_ctx + '2A_images',
                         classes=CLASSES,
                         covid_files=dir_ctx + 'co_train.txt',
                         non_covid_files=dir_ctx + 'nc_train.txt',
                         transform=train_transformer,
                         is_ctx=True)
    valset = CTDataset(root_dir=dir_ctx + '2A_images',
                       classes=CLASSES,
                       covid_files=dir_ctx + 'co_val.txt',
                       non_covid_files=dir_ctx + 'nc_val.txt',
                       transform=val_transformer)
    testset = CTDataset(root_dir=dir_ctx + '2A_images',
                        classes=CLASSES,
                        covid_files=dir_ctx + 'co_test.txt',
                        non_covid_files=dir_ctx + 'nc_test.txt',
                        transform=val_transformer,
                        is_ctx=True)

# =============================================================
# STEP: CREATE DATA-LOADERS
# =============================================================
train_loader = DataLoader(trainset, batch_size=batchsize, drop_last=False, shuffle=True, num_workers=1)
test_loader = DataLoader(testset, batch_size=batchsize, drop_last=False, shuffle=False, num_workers=1)

# =============================================================
# STEP: MAIN FUNCTION
# =============================================================
if __name__ == '__main__':

    # Initialization information
    divider = '===================================================='
    print('\n' + divider)
    print("MODEL:\t\t\t\t", model_name)
    print("DATASET:\t\t\t", SET_NAME)
    print("CLASSES:\t\t\t", CLASSES)
    if training:
        print("IMAGE BATCHES:\t\t", str(batchsize) + "x" + str(IMGSIZE) + "x" + str(IMGSIZE))
        valsize = 0
        if 'valset' in locals():
            valsize = len(valset)
        set_size = len(trainset) + len(testset) + valsize
        print("TOTAL IMAGES:\t\t", '{:,}'.format(set_size))
        print("EPOCHS:\t\t\t\t", str(EPOCHS))
    else:
        print("TOTAL IMAGES:\t\t", '{:,}'.format(len(testset)))

    # Record log & figure directories
    TRAIN_PATH = "./logs/train_logger/__" + model_name + "__run___training.log"
    TEST_PATH = "./logs/test_logger/__" + model_name + "__run___test.log"
    TEST2_PATH = "./logs/test_logger/--" + model_name + "__split___test.log"
    PLOT_PATH = "./figures/" + model_name + "_plot.png"

    steps = math.ceil(len(trainset) / batchsize)
    digits = math.floor(len(str(steps)) / 2)
    epochs = math.ceil(EPOCHS * 0.1)
    tag = '_pruned'
    acc_original = 0.0

    if not training and prune and quant:
        model_name += tag
        model = torch.load(dir_models_p + model_name + '.pth')    # Summons pruned model.

    if training:
        rem_old_file = False
        if os.path.exists(TRAIN_PATH):
            os.remove(TRAIN_PATH)
            rem_old_file = True
        if os.path.exists(TEST_PATH):
            os.remove(TEST_PATH)
            rem_old_file = True
        if os.path.exists(TEST2_PATH):
            os.remove(TEST2_PATH)
            rem_old_file = True
        if os.path.exists(PLOT_PATH):
            os.remove(PLOT_PATH)
            rem_old_file = True

        if rem_old_file:
            print("PRE-EXISTING LOGS: \t CLEARED")
        print(divider)

        fit(model=model, train_loader=train_loader, test_loader=test_loader, optimizer=optimizer,
            epochs=EPOCHS, model_name=model_name, divider=divider, print_freq=math.pow(10, digits),
            sub_folder=dir_models.replace(cut_dir, ''))
        print("\n> All Epochs completed!")
    else:
        acc_original = test(model=model, model_name=model_name, test_loader=test_loader, divider=divider, re_test=True)
        print(divider)
        acc1 = '{:.1f}%'.format(acc_original)
        print("\n> Testing Complete:\t\t\t ", '{:>6}'.format(acc1))

    if graph:
        print("\n> Generating Plots...")
        Plot(model_name).plot(only_test=(not training))
        print("> Plot Closed.")

    if prune and not quant:

        # STEP Prune Model
        # =============================================================
        model_pruned = prune_model(model=model, name=model_name, dir_models=dir_models_p, suffix=tag, im_size=IMGSIZE)
        model_name += tag

        # EVAL Pruned Model
        # =============================================================
        fit(model=model_pruned, train_loader=train_loader, test_loader=test_loader, optimizer=optimizer,
            epochs=epochs, model_name=model_name, divider=divider, print_freq=math.pow(10, digits),
            sub_folder=dir_models_p.replace(cut_dir, ''))

        model_pruned = torch.load(dir_models_p + model_name + ".pth")
        acc_pruned = test(model=model_pruned, model_name=model_name, test_loader=test_loader,
                          divider=divider, re_test=True)

        print(divider)
        acc1 = '{:.1f}%'.format(acc_original)
        acc2 = '{:.1f}%'.format(acc_pruned)
        print('Origin Model Accuracy:\t', '{:>6}'.format(acc1))
        print('Pruned Model Accuracy:\t', '{:>6}'.format(acc2))
        result = (acc_pruned - acc_original) / acc_original
        diff = '{:.2f}%'.format(abs(result) * 100)
        state_str = 'dropped' if result < 0 else 'rose'
        # gap = '\t\t' if abs(result) * 100 < 10.0 else '\t'
        print('Accuracy ' + state_str + ' by:' + '\t', '{:>6}'.format(diff))
        print(divider)

    if quant:
        dir_m = dir_models_q if not prune else dir_models_pq

        # STEP Quantize Model
        # =============================================================
        tag = '_quantized'
        model_quantized = quantize_model(model=model, name=model_name, dir_models=dir_m, suffix=tag)
        model_name += tag

        # EVAL Quantized Model
        # =============================================================
        acc_quantized = test(model=model_quantized, model_name=model_name, test_loader=test_loader,
                             divider=divider, re_test=True, quant=quant)

        print(divider)
        acc1 = '{:.1f}%'.format(acc_original)
        acc2 = '{:.1f}%'.format(acc_quantized)
        print('Origin Model Accuracy:\t', '{:>6}'.format(acc1))
        print('Quant. Model Accuracy:\t', '{:>6}'.format(acc2))
        result = (acc_quantized - acc_original) / acc_original
        diff = '{:.2f}%'.format(abs(result) * 100)
        state_str = 'dropped' if result < 0 else 'rose'
        # gap = '\t\t' if abs(result) * 100 < 10.0 else '\t'
        print('Accuracy ' + state_str + ' by:' + '\t', '{:>6}'.format(diff))
        print(divider)
