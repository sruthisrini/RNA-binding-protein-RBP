"""
classifier.py -h

positional arguments:
  train_path    Enter the path to the folder containing dataset
  {1,30}        Enter the number of labels. Label 1 is used for binary classifier and Label 30 is used for multi label classifier
  epoch         Enter the number of epochs for training
  patience_val  Enter a value for patience
  test_path     Enter the path to the folder containing the test dataset
  {1,30}        Enter the number of labels for testing. Label 1 is used for binary classifier and Label 30 is used for multi label classifier

options:
  -h, --help    show this help message and exit
 
-----------------------------------------------------------------------------------------------------------------------------------------------------

To clone the repository:
git clone "https://github.com/sruthisrini/RNA-binding-protein-RBP.git"

Example call:
python classifier.py "train_dataset.csv" 30 100 10 "test_dataset.csv" 30 (for multilabel)
python classifier.py "train_dataset.csv" 1 100 10 "test_dataset.csv" 1 (for binary)

"""

import torch
from torch import Tensor
import numpy as np
import pandas as pd
import torch.nn as nn
from torch.nn import BCEWithLogitsLoss
from torch.utils.data import DataLoader,Dataset
from torch.nn.utils.rnn import pad_sequence
from sklearn.model_selection import train_test_split
from transform import prepare_data,string_vectorizer,read_data_to_list
from model import RNNDataset,LSTMModel
import wandb
from sklearn.metrics import f1_score
import warnings
import argparse


def warn(*args, **kwargs):
    pass

warnings.warn = warn

criterion = BCEWithLogitsLoss() 
model_path=r"saved_model.pt"

def train(model, optimizer, train_loader, criterion, batch_size, device):
    model.train()
    global loss_train
    loss_all_train = 0
    f1_acc=0.0

    for batch_data, batch_labels, batch_lens in train_loader:
        
            optimizer.zero_grad()
            outputs, _ = model(batch_data, batch_lens, len(batch_labels))
            outputs = outputs.reshape([len(batch_lens), 1,args.labels])
            loss = criterion(outputs, batch_labels)
            loss_all_train += loss.item() * len(batch_labels)
            loss.backward()
            optimizer.step()
            sigmoid_outputs=torch.sigmoid(outputs)
            sigmoid_outputs[np.where(sigmoid_outputs>=0.5)]=1
            sigmoid_outputs[np.where(sigmoid_outputs<0.5)]=0
            sigmoid_outputs=sigmoid_outputs.reshape([len(batch_lens),args.labels])
            batch_labels=batch_labels.reshape([len(batch_lens),args.labels])
            f1_acc+=f1_score(batch_labels.detach().numpy().astype(int), sigmoid_outputs.detach().numpy().astype(int),average='weighted')
        
    f1_total_accuracy=f1_acc/len(train_loader)
    loss_train=loss_all_train / len(train_loader.dataset)
    return loss_train,f1_total_accuracy
    

def validation(test_loader, model, batch_size, criterion, device):
    
    model.eval()
    loss_all_validation=0
    global loss_validation
    f1_acc=0.0


    for batch_data, batch_labels, batch_lens in test_loader:
        
        outputs, _ = model(batch_data, batch_lens, len(batch_labels))
        outputs = outputs.reshape([len(batch_lens), 1,args.labels])
        loss = criterion(outputs, batch_labels)
        loss_all_validation += loss.item() * len(batch_labels)  
        sigmoid_outputs=torch.sigmoid(outputs)
        sigmoid_outputs[np.where(sigmoid_outputs>=0.5)]=1
        sigmoid_outputs[np.where(sigmoid_outputs<0.5)]=0
        sigmoid_outputs=sigmoid_outputs.reshape([len(batch_lens),args.labels])
        batch_labels=batch_labels.reshape([len(batch_lens),args.labels])
        f1_acc+=f1_score(batch_labels.detach().numpy().astype(int),sigmoid_outputs.detach().numpy().astype(int), average='weighted')

    f1_total_accuracy=f1_acc/len(test_loader)
    loss_validation=loss_all_validation / len(test_loader.dataset)
    return loss_validation,f1_total_accuracy


def accuracy(preds, y):
    """
    Accuracy calculation:
    Round scores > 0 to 1, and scores <= 0 to 0 (using sigmoid function).

    """

    rounded_preds = torch.round(torch.sigmoid(preds))
    
    correct = (rounded_preds[:][0] == y[:][0]).float()
    acc = correct.sum()/len(correct)
    return acc



def test(test_loader, model, device):
    
    model.eval()
    loss_all_test=0
    global loss_test
    f1_acc=0.0
    test_acc = 0.0
  
    for batch_data, batch_labels, batch_lens in test_loader:
        
        outputs, _ = model(batch_data, batch_lens, len(batch_labels))
        outputs = outputs.reshape([len(batch_lens), args.test_labels])
        batch_labels=batch_labels.reshape([len(batch_lens), args.test_labels])
        acc = accuracy(outputs, batch_labels)
        test_acc += acc.item()
        sigmoid_outputs=torch.sigmoid(outputs)
        sigmoid_outputs[np.where(sigmoid_outputs>=0.5)]=1
        sigmoid_outputs[np.where(sigmoid_outputs<0.5)]=0
        sigmoid_outputs=sigmoid_outputs.reshape([len(batch_lens),args.test_labels])
        batch_labels=batch_labels.reshape([len(batch_lens),args.test_labels])
        f1_acc+=f1_score(batch_labels.detach().numpy().astype(int), sigmoid_outputs.detach().numpy().astype(int),average='weighted')

        
    test_acc = test_acc / len(test_loader)
    f1_total_accuracy=f1_acc/len(test_loader)
    loss_test=loss_all_test / len(test_loader.dataset)
    return test_acc,f1_total_accuracy



def pad_collate(batch):
    (xs, ys) = zip(*batch)
    xs_lens = [len(x) for x in xs]
    xs_pad = pad_sequence(xs, batch_first=True, padding_value=0)
    ys = torch.FloatTensor([[y] for y in ys])
    return xs_pad, ys,xs_lens

def patience(model,patience_count):
    
    best_val_loss = 1000000000.0
    elapsed_patience = 0
    c_epochs = 0

    for epoch in range(1, args.epoch):
        c_epochs += 1
        if elapsed_patience >= patience_count:
            break

        train_loss,train_f1_score = train(model=projmlc_model,optimizer=optimizer, train_loader=train_loader, criterion=criterion, batch_size=batch_size, device="cpu")
        val_loss,val_f1_score = validation(test_loader=validation_loader,model=projmlc_model,batch_size=batch_size,criterion=criterion,device="cpu")
        
        print('Epoch {}: ({}, {})'.format(epoch, train_loss, val_loss))
        wandb.log({"train loss":train_loss,"validation loss" : val_loss})

        if val_loss < best_val_loss:
            elapsed_patience = 0
            best_val_loss = val_loss
            torch.save(model.state_dict(), model_path)
        else:
            elapsed_patience += 1
    
    return train_f1_score,val_f1_score

if __name__ == "__main__":
    tr_parser=argparse.ArgumentParser()
    tr_parser.add_argument('train_path',help="Enter the path to the folder containing dataset")
    tr_parser.add_argument('labels',type=int,help='Enter the number of labels. Label 1 is used for binary classifier and Label 30 is used for multi label classifier',choices=[1,30])
    tr_parser.add_argument('epoch',type=int,help="Enter the number of epochs for training")
    tr_parser.add_argument('patience_val',type=int,help="Enter a value for patience")
    tr_parser.add_argument("test_path",help="Enter the path to the folder containing the test dataset")
    tr_parser.add_argument('test_labels',type=int,help='Enter the number of labels for testing.Label 1 is used for binary classifier and Label 30 is used for multi label classifier',choices=[1,30])
    
    args=tr_parser.parse_args()
    
    csv_file_path = args.train_path

    if args.labels==1:
        rna_vecs,rna_labels = prepare_data(csv_file_path,1)
    else:
        rna_vecs,rna_labels = prepare_data(csv_file_path,30)

    wandb.init(project="project")
    projmlc_dataset = RNNDataset(rna_vecs, rna_labels)
    projmlc_model = LSTMModel(input_dim=4, n_class=args.labels, activation='sigmoid',device="cpu")
    batch_size=32
    
    train_dataset_final, val_dataset=train_test_split(projmlc_dataset, test_size=0.2, random_state=0)  
 
    train_loader = DataLoader(dataset=train_dataset_final,batch_size=batch_size,collate_fn=pad_collate, pin_memory=True) 
    
    validation_loader=DataLoader(dataset=val_dataset,batch_size=batch_size,collate_fn=pad_collate,pin_memory=True)

    csv_file_path2=args.test_path
    
    if args.test_labels==1:
        rna_vecs2,rna_labels2 = prepare_data(csv_file_path2,1)
    else:
        rna_vecs2,rna_labels2 = prepare_data(csv_file_path2,30)

    projmlc_dataset2 = RNNDataset(rna_vecs2, rna_labels2)
    
 
    test_loader=DataLoader(dataset=projmlc_dataset2,batch_size=batch_size,collate_fn=pad_collate,pin_memory=True)
    optimizer = torch.optim.AdamW(projmlc_model.parameters(), lr=0.00001)  

    print(patience(projmlc_model,args.patience_val))

    projmlc_model.load_state_dict(torch.load(model_path))
    projmlc_model.eval()
    print("test_acc,f1_total_accuracy:",test(test_loader=test_loader,model=projmlc_model,device="cpu"))
    

    def pred(seq):
        pred_input=string_vectorizer(seq)
        pred_input=pred_input.reshape([1,len(pred_input),4])
        outputs, _ = projmlc_model(pred_input, [len(pred_input)], 1)
        outputs=torch.sigmoid(outputs)
        print(outputs[0])
        p=outputs[0][0]
        p= [1 if i>=0.52 else 0 for i in p]
        return p
    
    df=pd.read_csv(csv_file_path)
    protein_names=df.columns.to_list()[1:]
    
    # pred_label=pred("CGAAGGACATAGGCGTCATCACAATGCAATAAAGACACACACAACCACACAGACGACTCGAATGACACAGACGTCATCACCATGCAACACACAGGACACACACAACCACGCAGACGACTCGAAGGACACAGGCGTCATCACAATGCAATACACAAGACACACACAACCACGCAG")
    # print([names for names, label in zip(protein_names,pred_label) if label == 1])

