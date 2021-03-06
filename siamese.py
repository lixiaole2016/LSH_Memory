import os

import torch
import torchvision
import torchvision.transforms as transforms

from torch.autograd import Variable
import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F

from torch.utils.data import Dataset, DataLoader
import omniglot

class Net(nn.Module):
    def __init__(self, input_shape):
        super(Net, self).__init__()
        ch, row, col = input_shape
        kernel = 3
        pad = int((kernel-1)/2.0)

        self.predict = nn.Linear(128, 2)

        self.convolution = nn.Sequential(
            nn.Conv2d(ch, 64, kernel, padding=pad),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel, padding=pad),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 128, kernel, padding=pad),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, kernel, padding=pad),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2,2)
        )

        self.fc = nn.Sequential(
            nn.Linear(row // 4 * col // 4 * 128, 128),
            nn.Sigmoid()
        )

    def embed(self, x):
        x = self.convolution(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return x

    def forward(self, x, y):
        embed_x = self.embed(x)
        embed_y = self.embed(y)
        l1_distance = torch.abs(embed_x - embed_y)
        result = self.predict(l1_distance)
        return result

epochs = 1000
rnd = 1000
M = 32 
N = 20
K = 250
DATA_FILE_FORMAT = os.path.join(os.getcwd(), '%s_omni.pkl')

train_filepath = DATA_FILE_FORMAT % 'train'
train_set = omniglot.TrainSiameseDataset(train_filepath)
train_sampler = omniglot.SiameseSampler(train_set, rnd, M, False)
trainloader = torch.utils.data.DataLoader(train_set, batch_size=M, shuffle=True, sampler=train_sampler, num_workers=4)

test_filepath = DATA_FILE_FORMAT % 'test'
test_set = omniglot.TestSiameseDataset(test_filepath)
test_sampler = omniglot.SiameseSampler(test_set, K, N, True)
testloader = torch.utils.data.DataLoader(test_set, batch_size=N, shuffle=False, sampler=test_sampler, num_workers=4)

#torch.cuda.set_device(1)
net = Net(input_shape=(1,28,28))
net.cuda()

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(net.parameters(), lr=1e-3)

for epoch in range(epochs):
    running_loss = 0
    for i, data in enumerate(trainloader, 0):
        optimizer.zero_grad()
        inputs, labels = data
        left, right = inputs
        left, right, labels = Variable(left.cuda()), Variable(right.cuda()), Variable(labels.cuda())
        y_hat = net(left, right)
        loss = criterion(y_hat, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.data[0]
        if i == len(trainloader)-1:
            print("[{0:d}, {1:5d}] loss: {2:.3f}".format((epoch+1), (i+1), (running_loss / len(trainloader))))
            running_loss = 0.0

print('Finished Training')

total = 0
correct = 0
print("Evaluating model on {0} unique {1}-way one-shot learning tasks ...".format(K,N))
for i, data in enumerate(testloader, 0):
    inputs, labels = data
    x, y = inputs
    x, y = Variable(x.cuda()), Variable(y.cuda())
    labels = labels.cuda()
    y_hat = net(x, y)
    _, predicted = torch.max(y_hat.data, 1)
    if torch.eq(predicted, labels).sum() == N:
        correct += 1
    total += 1

print('Accuracy {0}% for {1}-way one-shot learning: {2}'.format(100 * correct / total, N, correct))
