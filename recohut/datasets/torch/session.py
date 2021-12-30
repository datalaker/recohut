# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/datasets/torch/session.ipynb (unless otherwise specified).

__all__ = ['Dataset', 'YoochooseDataset', 'NowplayingDataset', 'DigineticaDataset', 'LastfmDataset']

# Cell
import numpy as np
import pandas as pd
import csv
from collections import defaultdict

import recohut
from ...utils.common_utils import download_url

import torch
from torch.utils import data

# Cell
class Dataset(data.Dataset):
    def __init__(self, fpath, maxlen, is_train=True):
            [train, valid, test, itemnum] = self.data_partition(fpath)
            print("Number of sessions:",len(train)+len(valid)+len(test))
            print("Number of items:", itemnum)

            action = 0
            for i in train:
                action += np.count_nonzero(i)
            for i in valid:
                action += np.count_nonzero(i)
            for i in test:
                action += np.count_nonzero(i)

            print("Number of actions:", action)
            print("Average length of sessions:", action/(len(train)+len(valid)+len(test)))

            self.data = train if is_train else test
            self.maxlen = maxlen
            self.itemnum = itemnum
            self.is_train = is_train

    def __len__(self):
            return len(self.data)

    def __train__(self, index):
            session = np.asarray(self.data[index], dtype=np.int64)
            if len(session) > self.maxlen:
                session = session[-self.maxlen:]
            else:
                session = np.pad(session, (self.maxlen-len(session), 0), 'constant', constant_values=0)
            curr_seq = session[:-1]
            curr_pos = session[1:]
            return curr_seq, curr_pos

    def __test__(self, index):
            session = self.data[index]
            seq = np.zeros([self.maxlen], dtype=np.int64)
            idx = self.maxlen - 1
            for i in reversed(session[:-1]): #everything except the last one
                seq[idx] = i
                idx -= 1
                if idx == -1: break
            return seq, session[-1]-1 #index of the item in the list of all items

    def __getitem__(self, index):
            if self.is_train:
                return self.__train__(index)
            else:
                return self.__test__(index)

    @staticmethod
    def data_partition(fname, percentage=[0.1, 0.2]):
        itemnum = 0

        sessions = defaultdict(list)
        session_train = []
        session_valid = []
        session_test = []
        # assume user/item index starting from 1
        session_id = 0
        f = open(fname, 'r')
        total_length = 0
        max_length = 0
        for line in f:

            items = [int(l) for l in line.rstrip().split(',')]

            if len(items) < 5: continue
            total_length += len(items)

            if max_length< len(items):
                max_length = len(items)

            itemnum = max(max(items), itemnum)
            sessions[session_id].append(items)
            session_id += 1

        print("Avg length:", total_length/session_id)
        print("Maximum length:", max_length)

        valid_perc = percentage[0]
        test_perc = percentage[1]

        total_sessions = session_id

        shuffle_indices = np.random.permutation(range(total_sessions)) #

        train_index = int(total_sessions*(1 - valid_perc - test_perc))
        valid_index = int(total_sessions*(1 - test_perc))

        if (train_index == valid_index): valid_index += 1 #break the tie

        train_indices = shuffle_indices[:train_index]
        valid_indices = shuffle_indices[train_index:valid_index]
        test_indices = shuffle_indices[valid_index:]

        for i in train_indices:
            session_train.extend(sessions[i])
        for i in valid_indices:
            session_valid.extend(sessions[i])
        for i in test_indices:
            session_test.extend(sessions[i])

        return [np.asarray(session_train), np.asarray(session_valid), np.asarray(session_test), itemnum]

    @staticmethod
    def nextitnet_format(fname, maxlen):

        sessions = []

        # assume user/item index starting from 1
        f = open(fname, 'r')

        for line in f:

            items = [int(l) for l in line.rstrip().split(',')]

            if len(items) < 5: continue

            seq = np.zeros([maxlen], dtype=np.int32)

            idx = maxlen - 1

            for i in reversed(items):
                seq[idx] = i
                idx -= 1
                if idx == -1: break

            sessions.append(seq)

        print("number of session:", len(sessions))

        return sessions

    @staticmethod
    def gru_format(fname, user_train, user_valid, user_test):

        session_id = 0
        train = []
        for session in user_train:
            for item in session:
                train.append([session_id, item, 0])
            session_id += 1

        valid = []
        for session in user_valid:
            for item in session:
                valid.append([session_id, item, 0])
            session_id += 1

        test = []
        for session in user_test:
            for item in session:
                test.append([session_id, item, 0])
            session_id += 1

        train_data = pd.DataFrame(train, columns= ['SessionId', 'ItemId', 'Time'])
        valid_data = pd.DataFrame(valid, columns= ['SessionId', 'ItemId', 'Time'])
        test_data = pd.DataFrame(test, columns= ['SessionId', 'ItemId', 'Time'])

        return train_data, valid_data, test_data

# Cell
class YoochooseDataset(Dataset):
    url = 'https://github.com/RecoHut-Datasets/yoochoose/raw/v3/yoochoose.csv'

    def __init__(self, root, maxlen, is_train=True):
        fpath = download_url(url=self.url, folder=root)
        super().__init__(fpath, maxlen, is_train)

# Cell
class NowplayingDataset(Dataset):
    url = 'https://github.com/RecoHut-Datasets/nowplaying/raw/v3/nowplaying.csv'

    def __init__(self, root, maxlen, is_train=True):
        fpath = download_url(url=self.url, folder=root)
        super().__init__(fpath, maxlen, is_train)

# Cell
class DigineticaDataset(Dataset):
    url = 'https://github.com/RecoHut-Datasets/diginetica/raw/v4/diginetica.csv'

    def __init__(self, root, maxlen, is_train=True):
        fpath = download_url(url=self.url, folder=root)
        super().__init__(fpath, maxlen, is_train)

# Cell
class LastfmDataset(Dataset):
    url = 'https://github.com/RecoHut-Datasets/lastfm/raw/v2/last_fm.csv'

    def __init__(self, root, maxlen, is_train=True):
        fpath = download_url(url=self.url, folder=root)
        super().__init__(fpath, maxlen, is_train)