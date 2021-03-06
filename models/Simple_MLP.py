import torch
import torch.nn as nn
import torch.nn.functional as F


class simple_MLP(nn.Module):
    def __init__(self):
        super(simple_MLP, self).__init__()
        self.fc1 = nn.Linear(28*28, 50)
        self.fc2 = nn.Linear(50, 10)

    def forward(self, x):
        x = x.view(-1, 28*28)
        x = F.relu(self.fc1(x))
        out = F.softmax(self.fc2(x), dim=1)
        return out

def MLP():
    return simple_MLP()
