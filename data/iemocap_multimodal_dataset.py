import os
import json
import random
from typing import List
import torch
import numpy as np
import h5py
from numpy import int32, int64
from torch.nn.utils.rnn import pad_sequence
from torch.nn.utils.rnn import pack_padded_sequence
from random import randrange, sample
from data.base_dataset import BaseDataset
import pickle

#labels = ['anger', 'disgust', 'sadness', 'joy', 'neutral', 'surprise', 'fear']
#labels = ['ang', 'dis', 'sad', 'hap', 'neu', 'sur', 'fea']
labels = ['neu', 'hap', 'sad', 'ang']
class iemocapmultimodaldataset(BaseDataset):
    @staticmethod
    def modify_commandline_options(parser, isTrain=None):
        parser.add_argument('--cvNo', default=1, type=int, help='which cross validation set')
        parser.add_argument('--A_type', default='comparE', type=str, help='which audio feat to use')
        parser.add_argument('--V_type', default='denseface', type=str, help='which visual feat to use')
        parser.add_argument('--L_type', default='bert_large', type=str, help='which lexical feat to use')
        parser.add_argument('--output_dim', default=4, type=int, help='how many label types in this dataset')
        parser.add_argument('--norm_method', default='trn', type=str, choices=['utt', 'trn'],
                            help='how to normalize input comparE feature')
        parser.add_argument('--corpus_name', type=str, default='MELD', help='which dataset to use')
        return parser

    def __init__(self, opt, set_name):
        ''' IEMOCAP dataset reader
            set_name in ['trn', 'val', 'tst']
        '''
        super().__init__(opt)

        # record & load basic settings
        cvNo = opt.cvNo
        print('11111')
        self.set_name = set_name
        pwd = os.path.abspath(__file__)
        pwd = os.path.dirname(pwd)
        config = json.load(open(os.path.join(pwd, 'config', f'{opt.corpus_name}at_config.json')))  # 特征地址
        self.norm_method = opt.norm_method
        self.corpus_name = opt.corpus_name



        
        if set_name == 'trn':
            self.all_A = []
            self.all_V = []
            self.all_L = []
            self.label = []
            
            for i in range(3):
                root_name = 'train_root' + str(i+1)
                print(root_name)
                
                data_path = config[root_name]
                file = open(data_path, "rb")
                data_split = pickle.load(file)
                file.close()    
                self.all_A += data_split['audio']
                self.all_V += data_split['vision']
                self.all_L += data_split['text']
                self.label += [labels.index(i) for i in data_split['emotion_labels']]
          

        if set_name == 'val':
            data_path = config['val_root']
            file = open(data_path, "rb")
            data_split = pickle.load(file)
            file.close()            

        if set_name == 'tst':
            data_path = config['test_root']
            file = open(data_path, "rb")
            data_split = pickle.load(file)
            file.close()            
        print('222222')

        if set_name != 'trn':
            self.all_A = data_split['audio']
            self.all_V = data_split['vision']
            self.all_L = data_split['text']
            self.label = [labels.index(i) for i in data_split['emotion_labels']]

        self.label = np.array(self.label, dtype=int64)
 
        self.manual_collate_fn = True

    def h5_to_dict(self, h5f):
        ret = {}
        for key in h5f.keys():
            ret[key] = h5f[key][()]
        return ret

    def __getitem__(self, index):
        # print(f'index = {index}')
        label = torch.tensor(self.label[index])

        A_feat = torch.from_numpy(self.all_A[index][()]).float()
        V_feat = torch.from_numpy(self.all_V[index][()]).float()
        L_feat = torch.from_numpy(self.all_L[index][()]).float()

        A_feat[torch.isnan(A_feat)] = 0
        V_feat[torch.isnan(V_feat)] = 0


        return {
            'A_feat': A_feat,
            'V_feat': V_feat,
            'L_feat': L_feat,
            'label': label,
            #'missing_index': missing_index,
            #'miss_type': miss_type
        } if self.set_name == 'trn' else {
            'A_feat': A_feat, #* missing_index[0],
            'V_feat': V_feat, #* missing_index[1],
            'L_feat': L_feat, #* missing_index[2],
            'label': label,
            #'missing_index': missing_index,
            #'miss_type': miss_type
        }

    def __len__(self):
        #return len(self.missing_index) if self.set_name != 'trn' else len(self.label)
        return len(self.label)

    def normalize_on_utt(self, features):
        mean_f = torch.mean(features, dim=0).unsqueeze(0).float()
        std_f = torch.std(features, dim=0).unsqueeze(0).float()
        std_f[std_f == 0.0] = 1.0
        features = (features - mean_f) / std_f
        return features

    def normalize_on_trn(self, features):
        features = (features - self.mean) / self.std
        return features

    def calc_mean_std(self):
        utt_ids = [utt_id for utt_id in self.all_A.keys()]
        feats = np.array([self.all_A[utt_id] for utt_id in utt_ids])
        _feats = feats.reshape(-1, feats.shape[2])
        mean = np.mean(_feats, axis=0)
        std = np.std(_feats, axis=0)
        std[std == 0.0] = 1.0
        return mean, std

    def collate_fn(self, batch):
        A = [sample['A_feat'] for sample in batch]
        V = [sample['V_feat'] for sample in batch]
        L = [sample['L_feat'] for sample in batch]
        # sec = list(range(0,768)) + list(range(768*2, 768*3))
        # L = [sample['L_feat'][:, sec] for sample in batch]
        lengths = torch.tensor([len(sample) for sample in A]).long()
        A = pad_sequence(A, batch_first=True, padding_value=0)
        V = pad_sequence(V, batch_first=True, padding_value=0)
        L = pad_sequence(L, batch_first=True, padding_value=0)
        label = torch.tensor([sample['label'] for sample in batch])
        # int2name = [sample['int2name'] for sample in batch]
        #missing_index = torch.cat([sample['missing_index'].unsqueeze(0) for sample in batch], axis=0)
        #miss_type = [sample['miss_type'] for sample in batch]
        return {
            'A_feat': A,
            'V_feat': V,
            'L_feat': L,
            'label': label,
            'lengths': lengths,
            #'missing_index': missing_index,
            #'miss_type': miss_type
        }

