"""Train MNIST with PyTorch."""
from __future__ import print_function
import torch
import torch.optim as optim
import torch.backends.cudnn as cudnn
import torchvision
import torchvision.transforms as transforms

import os
import argparse

from models import *

from adabound import AdaBound


def get_parser():
    parser = argparse.ArgumentParser(description='PyTorch MNIST Training')
    parser.add_argument('--model', default='SLP_model', type=str, help='model',
                        choices=['resnet', 'densenet', 'Simple_MLP','MLP_Dropout','SLP_model'])
    parser.add_argument('--optim', default='adam', type=str, help='optimizer',
                        choices=['sgd', 'adagrad', 'adam', 'amsgrad', 'adabound', 'amsbound'])
    parser.add_argument('--lr', default=1e-2, type=float, help='learning rate')
    parser.add_argument('--final_lr', default=1e-4, type=float,
                        help='final learning rate of AdaBound')
    parser.add_argument('--gamma', default=0.5, type=float,
                        help='convergence speed term of AdaBound')
    parser.add_argument('--momentum', default=0.9, type=float, help='momentum term')
    parser.add_argument('--beta1', default=0.9, type=float, help='Adam coefficients beta_1')
    parser.add_argument('--beta2', default=0.99, type=float, help='Adam coefficients beta_2')
    parser.add_argument('--resume', '-r', action='store_true', help='resume from checkpoint')
    parser.add_argument('--weight_decay', default=5e-4, type=float,
                        help='weight decay for optimizers')
    return parser


def build_dataset(): 
    print('==> Preparing data..')
    transform_train = transforms.Compose([
        # transforms.RandomCrop(32, padding=4),
        # transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        # transforms.Normalize((0.4914), (0.2023)),
    ])

    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Lambda(lambda x: x.view(-1))
        # transforms.Normalize((0.4914), (0.2023)),
    ])

    trainset = torchvision.datasets.MNIST(root='./data', train=True, download=True,
                                            transform=transform_train)
    train_loader = torch.utils.data.DataLoader(trainset, batch_size=128, shuffle=True)

    testset = torchvision.datasets.MNIST(root='./data', train=False, download=True,
                                           transform=transform_test)
    test_loader = torch.utils.data.DataLoader(testset, batch_size=100, shuffle=False)

    return train_loader, test_loader


def get_ckpt_name(model='SLP_model', optimizer='adam', lr=1e-2, final_lr=1e-4, momentum=0.9,
                  beta1=0.9, beta2=0.99, gamma=0.5):
    name = {
        'sgd': 'lr{}-momentum{}'.format(lr, momentum),
        'adagrad': 'lr{}'.format(lr),
        'adam': 'lr{}-betas{}-{}'.format(lr, beta1, beta2),
        'amsgrad': 'lr{}-betas{}-{}'.format(lr, beta1, beta2),
        'adabound': 'lr{}-betas{}-{}-final_lr{}-gamma{}'.format(lr, beta1, beta2, final_lr, gamma),
        'amsbound': 'lr{}-betas{}-{}-final_lr{}-gamma{}'.format(lr, beta1, beta2, final_lr, gamma),
    }[optimizer]
    return '{}-{}-{}'.format(model, optimizer, name)


def load_checkpoint(ckpt_name):
    print('==> Resuming from checkpoint..')
    path = os.path.join('checkpoint', ckpt_name)
    assert os.path.isdir('checkpoint'), 'Error: no checkpoint directory found!'
    assert os.path.exists(path), 'Error: checkpoint {} not found'.format(ckpt_name)
    return torch.load(ckpt_name)


def build_model(args, device, ckpt=None):
    print('==> Building model..')
    net = {
        'resnet': ResNet34,
        'densenet': DenseNet121,
        'Simple_MLP': MLP,
        'MLP_Dropout': MLP_drop,
        'SLP_model': S_L_P,
    }[args.model]()
    net = net.to(device)
    if device == 'cuda':
        net = torch.nn.DataParallel(net)
        cudnn.benchmark = True

    if ckpt:
        net.load_state_dict(ckpt['net'])

    return net


def create_optimizer(args, model_params):
    if args.optim == 'sgd':
#         return optim.SGD(model_params, args.lr, momentum=args.momentum,
#                          weight_decay=args.weight_decay)
        return optim.SGD(model_params, args.lr, momentum=args.momentum)
    elif args.optim == 'adagrad':
        return optim.Adagrad(model_params, args.lr)#, weight_decay=args.weight_decay)
    elif args.optim == 'adam':
#         return optim.Adam(model_params, args.lr, betas=(args.beta1, args.beta2),
#                           weight_decay=args.weight_decay)
        return optim.Adam(model_params, args.lr, betas=(args.beta1, args.beta2))
    elif args.optim == 'amsgrad':
        return optim.Adam(model_params, args.lr, betas=(args.beta1, args.beta2),
                          weight_decay=args.weight_decay, amsgrad=True)
    elif args.optim == 'adabound':
        return AdaBound(model_params, args.lr, betas=(args.beta1, args.beta2),
                        final_lr=args.final_lr, gamma=args.gamma)
#                         weight_decay=args.weight_decay)
    else:
        assert args.optim == 'amsbound'
        return AdaBound(model_params, args.lr, betas=(args.beta1, args.beta2),
                        final_lr=args.final_lr, gamma=args.gamma,
                        weight_decay=args.weight_decay, amsbound=True)


def train(net, epoch, device, data_loader, optimizer, criterion):
    print('\nEpoch: %d' % epoch)
    net.train()
    train_loss = 0
    correct = 0
    total = 0
    for batch_idx, (inputs, targets) in enumerate(data_loader):
        inputs, targets = inputs.to(device), targets.to(device)
        optimizer.zero_grad()
        outputs = net(inputs)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()

        train_loss += loss.item()
        _, predicted = outputs.max(1)
        total += targets.size(0)
        correct += predicted.eq(targets).sum().item()

    accuracy = 100. * correct / total
    print('train acc %.3f' % accuracy)

    return accuracy


def test(net, device, data_loader, criterion):
    net.eval()
    test_loss = 0
    correct = 0
    total = 0
    with torch.no_grad():
        for batch_idx, (inputs, targets) in enumerate(data_loader):
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = net(inputs)
            loss = criterion(outputs, targets)

            test_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

    accuracy = 100. * correct / total
    print(' test acc %.3f' % accuracy)

    return accuracy

parser = get_parser()
args = parser.parse_args()

train_loader, test_loader = build_dataset()
device = 'cuda:0' if torch.cuda.is_available() else 'cpu'

ckpt_name = get_ckpt_name(model=args.model, optimizer=args.optim, lr=args.lr,
                              final_lr=args.final_lr, momentum=args.momentum,
                              beta1=args.beta1, beta2=args.beta2, gamma=args.gamma)
if args.resume:
    ckpt = load_checkpoint(ckpt_name)
    best_acc = ckpt['acc']
    start_epoch = ckpt['epoch']
else:
    ckpt = None
    best_acc = 0
    start_epoch = -1

net = build_model(args, device, ckpt=ckpt)
criterion = nn.CrossEntropyLoss()
optimizer = create_optimizer(args, net.parameters())
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=18, gamma=0.5,
                                          last_epoch=start_epoch)

train_accuracies = []
test_accuracies = []

for epoch in range(start_epoch + 1, 100):
    scheduler.step()
    train_acc = train(net, epoch, device, train_loader, optimizer, criterion)
    test_acc = test(net, device, test_loader, criterion)

# Save checkpoint.
    print('Saving..')
    state = {
        'net': net.state_dict(),
        'acc': test_acc,
        'epoch': epoch,
    }
    if not os.path.isdir('checkpoint'):
         os.mkdir('checkpoint')
    torch.save(state, os.path.join('checkpoint', ckpt_name))
    best_acc = test_acc

    train_accuracies.append(train_acc)
    test_accuracies.append(test_acc)
    if not os.path.isdir('curve'):
        os.mkdir('curve')
    torch.save({'train_acc': train_accuracies, 'test_acc': test_accuracies},
                os.path.join('curve', ckpt_name))
       




