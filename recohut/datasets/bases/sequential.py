# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/datasets/bases/datasets.bases.sequential.ipynb (unless otherwise specified).

__all__ = ['SequentialDataset', 'SequentialDataModule']

# Cell
from typing import Any, Iterable, List, Optional, Tuple, Union, Callable

import random
import os
import numpy as np
import pandas as pd

import torch
from torch.utils.data import Dataset, DataLoader

from pytorch_lightning import LightningDataModule

from .common import Dataset as BaseDataset

# Cell
class SequentialDataset(Dataset, BaseDataset):
    def __init__(self,
                 data_dir,
                 data_type='train',
                 history_size=8,
                 step_size=1,
                 seed=42,
                 mask=1,
                 *args,
                 **kwargs):
        """
        Args:
            data_dir: Where to save/load the data
            data_type: train/valid/test
        """
        self.data_type = data_type
        self.history_size = history_size
        self.step_size = step_size
        self.seed = seed
        self.mask = mask

        super().__init__(data_dir)

        self._process()

    @property
    def raw_file_names(self):
        raise NotImplementedError

    @property
    def processed_file_names(self):
        return ['data.pt']

    def download(self):
        raise NotImplementedError

    def load_ratings_df(self):
        raise NotImplementedError

    def map_column(self, df: pd.DataFrame, col_name: str):
        """Maps column values to integers.
        """
        values = sorted(list(df[col_name].unique()))
        mapping = {k: i + 2 for i, k in enumerate(values)}
        inverse_mapping = {v: k for k, v in mapping.items()}
        df[col_name + "_mapped"] = df[col_name].map(mapping)
        return df, mapping, inverse_mapping

    def get_context(self, df: pd.DataFrame, split: str, context_size: int = 120, val_context_size: int = 5, seed: int = 42):
        """Create a training / validation samples.
        """
        random.seed(seed)
        if split == "train":
            end_index = random.randint(10, df.shape[0] - val_context_size)
        elif split in ["valid", "test"]:
            end_index = df.shape[0]
        else:
            raise ValueError
        start_index = max(0, end_index - context_size)
        context = df[start_index:end_index]
        return context

    def pad_list(self, list_integers, history_size: int, pad_val: int = 0, mode="left"):
        """Pad list from left or right
        """
        if len(list_integers) < history_size:
            if mode == "left":
                list_integers = [pad_val] * (history_size - len(list_integers)) + list_integers
            else:
                list_integers = list_integers + [pad_val] * (history_size - len(list_integers))
        return list_integers

    def mask_list(self, l1, p=0.8):
        random.seed(self.seed)
        l1 = [a if random.random() < p else self.mask for a in l1]
        return l1

    def mask_last_elements_list(self, l1, val_context_size: int = 5):
        l1 = l1[:-val_context_size] + self.mask_list(l1[-val_context_size:], p=0.5)
        return l1

    def make_user_history(self, data):
        user_history = [ [] for _ in range(self.num_users) ]
        for u, i, r in data: user_history[u].append(i)
        return user_history

    # def pad(self, arr, max_len = None, pad_with = -1, side = 'right'):
    #     seq_len = max_len if max_len is not None else max(map(len, arr))
    #     seq_len = min(seq_len, 200) # You don't need more than this

    #     for i in range(len(arr)):
    #         while len(arr[i]) < seq_len:
    #             pad_elem = arr[i][-1] if len(arr[i]) > 0 else 0
    #             pad_elem = pad_elem if pad_with == -1 else pad_with
    #             if side == 'right': arr[i].append(pad_elem)
    #             else: arr[i] = [ pad_elem ] + arr[i]
    #         arr[i] = arr[i][-seq_len:] # Keep last `seq_len` items
    #     return arr

    # def sequential_pad(self, arr, max_seq_len, total_items):
    #     # Padding left side so that we can simply take out [:, -1, :] in the output
    #     return self.pad(
    #         arr, max_len = max_seq_len,
    #         pad_with = total_items, side = 'left'
    #     )

    # def scatter(self, batch, tensor_kind, last_dimension):
    #     ret = tensor_kind(len(batch), last_dimension).zero_()

    #     if not torch.is_tensor(batch):
    #         if ret.is_cuda: batch = torch.cuda.LongTensor(batch)
    #         else: batch = torch.LongTensor(batch)

    #     return ret.scatter_(1, batch, 1)

    # def get_item_count_map(self, data):
    #     item_count = defaultdict(int)
    #     for u, i, r in data: item_count[i] += 1
    #     return item_count

    # def get_item_propensity(self, data, num_items, A = 0.55, B = 1.5):
    #     item_freq_map = self.get_item_count_map()
    #     item_freq = [ item_freq_map[i] for i in range(num_items) ]
    #     num_instances = len(data)

    #     C = (np.log(num_instances)-1)*np.power(B+1, A)
    #     wts = 1.0 + C*np.power(np.array(item_freq)+B, -A)
    #     return np.ravel(wts)

    def create_sequences(self, values, window_size, step_size):
        sequences = []
        start_index = 0
        while True:
            end_index = start_index + window_size
            seq = values[start_index:end_index]
            if len(seq) < window_size:
                seq = values[-window_size:]
                if len(seq) == window_size:
                    sequences.append(seq)
                break
            sequences.append(seq)
            start_index += step_size
        return sequences

    def process(self):
        df = self.load_ratings_df()
        df.sort_values(by="timestamp", inplace=True)
        df, self.mapping, self.inverse_mapping = self.map_column(df, col_name="sid")
        self.grp_by = df.groupby(by="uid")
        self.groups = list(self.grp_by.groups)

    def __len__(self):
            return len(self.groups)

    def __getitem__(self, index):
        group = self.groups[index]
        df = self.grp_by.get_group(group)
        context = self.get_context(df, split=self.data_type, context_size=self.history_size)
        trg_items = context["sid_mapped"].tolist()
        if self.data_type == "train":
            src_items = self.mask_list(trg_items)
        else:
            src_items = self.mask_last_elements_list(trg_items)
        pad_mode = "left" if random.random() < 0.5 else "right"
        trg_items = self.pad_list(trg_items, history_size=self.history_size, mode=pad_mode)
        src_items = self.pad_list(src_items, history_size=self.history_size, mode=pad_mode)
        src_items = torch.tensor(src_items, dtype=torch.long)
        trg_items = torch.tensor(trg_items, dtype=torch.long)
        return src_items, trg_items

# Cell
class SequentialDataModule(LightningDataModule):

    dataset_cls: str = ""

    def __init__(self,
                 data_dir: Optional[str] = None,
                 num_workers: int = 0,
                 normalize: bool = False,
                 batch_size: int = 32,
                 shuffle: bool = True,
                 pin_memory: bool = True,
                 drop_last: bool = False,
                 *args,
                 **kwargs) -> None:
        """
        Args:
            data_dir: Where to save/load the data
            num_workers: How many workers to use for loading data
            normalize: If true applies rating normalize
            batch_size: How many samples per batch to load
            shuffle: If true shuffles the train data every epoch
            pin_memory: If true, the data loader will copy Tensors into CUDA pinned memory before
                        returning them
            drop_last: If true drops the last incomplete batch
        """
        super().__init__(data_dir)

        self.data_dir = data_dir if data_dir is not None else os.getcwd()
        self.num_workers = num_workers
        self.normalize = normalize
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.pin_memory = pin_memory
        self.drop_last = drop_last
        self.kwargs = kwargs

    def prepare_data(self, *args: Any, **kwargs: Any) -> None:
        """Saves files to data_dir."""
        self.data = self.dataset_cls(self.data_dir, **self.kwargs)

    def setup(self, stage: Optional[str] = None) -> None:
        """Creates train, val, and test dataset."""
        if stage == "fit" or stage is None:
            self.dataset_train = self.dataset_cls(self.data_dir, data_type='train', **self.kwargs)
            self.dataset_val = self.dataset_cls(self.data_dir, data_type='valid', **self.kwargs)
        if stage == "test" or stage is None:
            self.dataset_test = self.dataset_cls(self.data_dir, data_type='test', **self.kwargs)

    def train_dataloader(self, *args: Any, **kwargs: Any) -> DataLoader:
        """The train dataloader."""
        return self._data_loader(self.dataset_train, shuffle=self.shuffle)

    def val_dataloader(self, *args: Any, **kwargs: Any) -> Union[DataLoader, List[DataLoader]]:
        """The val dataloader."""
        return self._data_loader(self.dataset_val)

    def test_dataloader(self, *args: Any, **kwargs: Any) -> Union[DataLoader, List[DataLoader]]:
        """The test dataloader."""
        return self._data_loader(self.dataset_test)

    def _data_loader(self, dataset: Dataset, shuffle: bool = False) -> DataLoader:
        return DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=shuffle,
            num_workers=self.num_workers,
            drop_last=self.drop_last,
            pin_memory=self.pin_memory,
        )