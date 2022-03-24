# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/datasets/datasets.retailrocket.ipynb (unless otherwise specified).

__all__ = ['RetailRocketDataset', 'RetailRocketDatasetv2']

# Cell
from typing import List, Optional, Callable, Union, Any, Tuple

import os
import os.path as osp
from collections.abc import Sequence
import sys

import numpy as np
import pandas as pd
from datetime import timezone, datetime, timedelta
import time

from ..utils.common_utils import download_url, extract_zip, makedirs
from .bases.common import Dataset
from .bases.session_graph import SessionGraphDataset

# Cell
class RetailRocketDataset(SessionGraphDataset):
    train_url = "https://github.com/RecoHut-Datasets/retail_rocket/raw/v1/train.txt"
    test_url = "https://github.com/RecoHut-Datasets/retail_rocket/raw/v1/test.txt"
    all_train_seq_url = "https://github.com/RecoHut-Datasets/retail_rocket/raw/v1/all_train_seq.txt"

    def __init__(self, root, shuffle=False, n_node=40727, is_train=True):
        self.n_node = n_node
        self.shuffle = shuffle
        self.is_train = is_train
        super().__init__(root, shuffle, n_node)

    @property
    def raw_file_names(self) -> str:
        if self.is_train:
            return ['train.txt', 'all_train_seq.txt']
        return ['test.txt', 'all_train_seq.txt']

    def download(self):
        download_url(self.all_train_seq_url, self.raw_dir)
        if self.is_train:
            download_url(self.train_url, self.raw_dir)
        else:
            download_url(self.test_url, self.raw_dir)

# Internal Cell
def to_list(value: Any) -> Sequence:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return value
    else:
        return [value]

def files_exist(files: List[str]) -> bool:
    # NOTE: We return `False` in case `files` is empty, leading to a
    # re-processing of files on every instantiation.
    return len(files) != 0 and all([osp.exists(f) for f in files])

# Cell
class RetailRocketDatasetv2(Dataset):
    r"""Load and process RetailRocket dataset.

    Args:
        root (string): Root directory where the dataset should be saved.
        process_method (string):
            last: last day => test set
            last_min_date: last day => test set, but from a minimal date onwards
            days_test: last N days => test set
            slice: create multiple train-test-combinations with a sliding window approach
        min_date (string, optional): Minimum date
        session_length (int, optional): Session time length :default = 30 * 60 #30 minutes
        min_session_length (int, optional): Minimum number of items for a session to be valid
        min_item_support (int, optional): Minimum number of interactions for an item to be valid
        num_slices (int, optional): Offset in days from the first date in the data set
        days_offset (int, optional): Number of days the training start date is shifted after creating one slice
        days_shift (int, optional): Days shift
        days_train (int, optional): Days in train set in each slice
        days_test (int, optional): Days in test set in each slice
    """

    url = 'https://github.com/RecoHut-Datasets/retail_rocket/raw/v2/retailrocket.zip'

    def __init__(self, root, process_method, min_date='2015-09-02',
                 session_length=30*60, min_session_length=2, min_item_support=5,
                 num_slices=5, days_offset=0, days_shift=27, days_train=25, days_test=2):
        super().__init__(root)
        self.process_method = process_method
        self.min_date = min_date
        self.session_length = session_length
        self.min_session_length = min_session_length
        self.min_item_support = min_item_support
        self.num_slices = num_slices
        self.days_offset = days_offset
        self.days_shift = days_shift
        self.days_train = days_train
        self.days_test = days_test
        self.data = None
        self.cart = None

        self._process()

    @property
    def raw_file_names(self) -> str:
        return 'events.csv'

    @property
    def processed_file_names(self) -> str:
        return 'data.pkl'

    def download(self):
        path = download_url(self.url, self.raw_dir)
        extract_zip(path, self.raw_dir)
        from shutil import move, rmtree
        move(osp.join(self.raw_dir, 'retailrocket', 'events.csv'),
             osp.join(self.raw_dir, 'events.csv'))
        rmtree(osp.join(self.raw_dir, 'retailrocket'))
        os.unlink(path)

    def load(self):
        #load csv
        data = pd.read_csv(osp.join(self.raw_dir,self.raw_file_names), sep=',',
                           header=0, usecols=[0,1,2,3],
                           dtype={0:np.int64, 1:np.int32, 2:str, 3:np.int32})
        #specify header names
        data.columns = ['Time','UserId','Type','ItemId']
        data['Time'] = (data.Time / 1000).astype(int)
        data.sort_values(['UserId','Time'], ascending=True, inplace=True)

        #sessionize
        data['TimeTmp'] = pd.to_datetime(data.Time, unit='s')
        data.sort_values(['UserId','TimeTmp'], ascending=True, inplace=True)

        data['TimeShift'] = data['TimeTmp'].shift(1)
        data['TimeDiff'] = (data['TimeTmp'] - data['TimeShift']).dt.total_seconds().abs()
        data['SessionIdTmp'] = (data['TimeDiff'] > self.session_length).astype(int)
        data['SessionId'] = data['SessionIdTmp'].cumsum( skipna=False)
        del data['SessionIdTmp'], data['TimeShift'], data['TimeDiff']

        data.sort_values(['SessionId','Time'], ascending=True, inplace=True)

        cart = data[data.Type == 'addtocart']
        data = data[data.Type == 'view']
        del data['Type']

        # output
        print(data.Time.min())
        print(data.Time.max())
        data_start = datetime.fromtimestamp( data.Time.min(), timezone.utc)
        data_end = datetime.fromtimestamp( data.Time.max(), timezone.utc)
        del data['TimeTmp']

        print('Loaded data set\n\tEvents: {}\n\tSessions: {}\n\tItems: {}\n\tSpan: {} / {}\n\n'.
              format(len(data), data.SessionId.nunique(), data.ItemId.nunique(), data_start.date().isoformat(), data_end.date().isoformat()))

        self.data = data
        self.cart = cart

    def filter_data(self):
        data = self.data

        #filter session length
        session_lengths = data.groupby('SessionId').size()
        data = data[np.in1d(data.SessionId, session_lengths[session_lengths>1].index)]

        #filter item support
        item_supports = data.groupby('ItemId').size()
        data = data[np.in1d(data.ItemId, item_supports[item_supports>= self.min_item_support].index)]

        #filter session length
        session_lengths = data.groupby('SessionId').size()
        data = data[np.in1d(data.SessionId, session_lengths[session_lengths>= self.min_session_length].index)]

        #output
        data_start = datetime.fromtimestamp(data.Time.min(), timezone.utc)
        data_end = datetime.fromtimestamp(data.Time.max(), timezone.utc)

        print('Filtered data set\n\tEvents: {}\n\tSessions: {}\n\tItems: {}\n\tSpan: {} / {}\n\n'.
              format(len(data), data.SessionId.nunique(), data.ItemId.nunique(), data_start.date().isoformat(), data_end.date().isoformat()))

        self.data = data

    def filter_min_date(self):
        data = self.data

        min_datetime = datetime.strptime(self.min_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')

        #filter
        session_max_times = data.groupby('SessionId').Time.max()
        session_keep = session_max_times[session_max_times > min_datetime.timestamp()].index

        data = data[np.in1d(data.SessionId, session_keep)]

        #output
        data_start = datetime.fromtimestamp(data.Time.min(), timezone.utc)
        data_end = datetime.fromtimestamp(data.Time.max(), timezone.utc)

        print('Filtered data set\n\tEvents: {}\n\tSessions: {}\n\tItems: {}\n\tSpan: {} / {}\n\n'.
              format(len(data), data.SessionId.nunique(), data.ItemId.nunique(), data_start.date().isoformat(), data_end.date().isoformat()))

        self.data = data

    def split_data_org(self):
        data = self.data
        tmax = data.Time.max()
        session_max_times = data.groupby('SessionId').Time.max()
        session_train = session_max_times[session_max_times < tmax-86400].index
        session_test = session_max_times[session_max_times >= tmax-86400].index
        train = data[np.in1d(data.SessionId, session_train)]
        test = data[np.in1d(data.SessionId, session_test)]
        test = test[np.in1d(test.ItemId, train.ItemId)]
        tslength = test.groupby('SessionId').size()
        test = test[np.in1d(test.SessionId, tslength[tslength>=2].index)]
        print('Full train set\n\tEvents: {}\n\tSessions: {}\n\tItems: {}'.format(len(train), train.SessionId.nunique(), train.ItemId.nunique()))
        train.to_csv(osp.join(self.processed_dir,'events_train_full.txt'), sep='\t', index=False)
        print('Test set\n\tEvents: {}\n\tSessions: {}\n\tItems: {}'.format(len(test), test.SessionId.nunique(), test.ItemId.nunique()))
        test.to_csv(osp.join(self.processed_dir,'events_test.txt'), sep='\t', index=False)

        tmax = train.Time.max()
        session_max_times = train.groupby('SessionId').Time.max()
        session_train = session_max_times[session_max_times < tmax-86400].index
        session_valid = session_max_times[session_max_times >= tmax-86400].index
        train_tr = train[np.in1d(train.SessionId, session_train)]
        valid = train[np.in1d(train.SessionId, session_valid)]
        valid = valid[np.in1d(valid.ItemId, train_tr.ItemId)]
        tslength = valid.groupby('SessionId').size()
        valid = valid[np.in1d(valid.SessionId, tslength[tslength>=2].index)]
        print('Train set\n\tEvents: {}\n\tSessions: {}\n\tItems: {}'.format(len(train_tr), train_tr.SessionId.nunique(), train_tr.ItemId.nunique()))
        train_tr.to_csv(osp.join(self.processed_dir,'events_train_tr.txt'), sep='\t', index=False)
        print('Validation set\n\tEvents: {}\n\tSessions: {}\n\tItems: {}'.format(len(valid), valid.SessionId.nunique(), valid.ItemId.nunique()))
        valid.to_csv(osp.join(self.processed_dir,'events_train_valid.txt'), sep='\t', index=False)

    def split_data(self):
        data = self.data
        data_end = datetime.fromtimestamp(data.Time.max(), timezone.utc)
        test_from = data_end - timedelta(self.days_test)

        session_max_times = data.groupby('SessionId').Time.max()
        session_train = session_max_times[session_max_times < test_from.timestamp()].index
        session_test = session_max_times[session_max_times >= test_from.timestamp()].index
        train = data[np.in1d(data.SessionId, session_train)]
        test = data[np.in1d(data.SessionId, session_test)]
        test = test[np.in1d(test.ItemId, train.ItemId)]
        tslength = test.groupby('SessionId').size()
        test = test[np.in1d(test.SessionId, tslength[tslength>=2].index)]
        print('Full train set\n\tEvents: {}\n\tSessions: {}\n\tItems: {}'.format(len(train), train.SessionId.nunique(), train.ItemId.nunique()))
        train.to_csv(osp.join(self.processed_dir,'events_train_full.txt'), sep='\t', index=False)
        print('Test set\n\tEvents: {}\n\tSessions: {}\n\tItems: {}'.format(len(test), test.SessionId.nunique(), test.ItemId.nunique()))
        test.to_csv(osp.join(self.processed_dir,'events_test.txt'), sep='\t', index=False)

    def slice_data(self):
        for slice_id in range(0, self.num_slices):
            self.split_data_slice(slice_id, self.days_offset+(slice_id*self.days_shift))

    def split_data_slice(self, slice_id, days_offset):
        data = self.data
        data_start = datetime.fromtimestamp(data.Time.min(), timezone.utc)
        data_end = datetime.fromtimestamp(data.Time.max(), timezone.utc)

        print('Full data set {}\n\tEvents: {}\n\tSessions: {}\n\tItems: {}\n\tSpan: {} / {}'.
            format(slice_id, len(data), data.SessionId.nunique(), data.ItemId.nunique(), data_start.isoformat(), data_end.isoformat()))

        start = datetime.fromtimestamp(data.Time.min(), timezone.utc ) + timedelta(days_offset)
        middle =  start + timedelta(self.days_train)
        end =  middle + timedelta(self.days_test)

        #prefilter the timespan
        session_max_times = data.groupby('SessionId').Time.max()
        greater_start = session_max_times[session_max_times >= start.timestamp()].index
        lower_end = session_max_times[session_max_times <= end.timestamp()].index
        data_filtered = data[np.in1d(data.SessionId, greater_start.intersection(lower_end))]

        print('Slice data set {}\n\tEvents: {}\n\tSessions: {}\n\tItems: {}\n\tSpan: {} / {} / {}'.
            format( slice_id, len(data_filtered), data_filtered.SessionId.nunique(), data_filtered.ItemId.nunique(), start.date().isoformat(), middle.date().isoformat(), end.date().isoformat() ) )

        #split to train and test
        session_max_times = data_filtered.groupby('SessionId').Time.max()
        sessions_train = session_max_times[session_max_times < middle.timestamp()].index
        sessions_test = session_max_times[session_max_times >= middle.timestamp()].index

        train = data[np.in1d(data.SessionId, sessions_train)]

        print('Train set {}\n\tEvents: {}\n\tSessions: {}\n\tItems: {}\n\tSpan: {} / {}'.
            format( slice_id, len(train), train.SessionId.nunique(), train.ItemId.nunique(), start.date().isoformat(), middle.date().isoformat() ) )

        train.to_csv(osp.join(self.processed_dir,'events_train_full.'+str(slice_id)+'.txt'), sep='\t', index=False)

        test = data[np.in1d(data.SessionId, sessions_test)]
        test = test[np.in1d(test.ItemId, train.ItemId)]

        tslength = test.groupby('SessionId').size()
        test = test[np.in1d(test.SessionId, tslength[tslength>=2].index)]

        print('Test set {}\n\tEvents: {}\n\tSessions: {}\n\tItems: {}\n\tSpan: {} / {} \n\n'.
            format( slice_id, len(test), test.SessionId.nunique(), test.ItemId.nunique(), middle.date().isoformat(), end.date().isoformat() ) )

        test.to_csv(osp.join(self.processed_dir,'events_test.'+str(slice_id)+'.txt'), sep='\t', index=False)

    def store_buys(self):
        self.cart.to_csv(osp.join(self.processed_dir,'events_buys.txt'), sep='\t', index=False)

    def process(self):
        self.load()
        self.filter_data()
        if self.process_method == 'last':
            self.split_data_org()
        elif self.process_method == 'last_min_date':
            self.filter_min_date()
            self.split_data_org()
        elif self.process_method == 'days_test':
            self.split_data()
        elif self.process_method == 'slice':
            self.slice_data()
        self.store_buys()