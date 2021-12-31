# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/datasets/gowalla.ipynb (unless otherwise specified).

__all__ = ['GowallaDataset']

# Cell
import os
import os.path as osp
import numpy as np
import pandas as pd
from pandas import Timedelta

from .base import SessionDatasetv3
from ..utils.common_utils import download_url, extract_gz

# Cell
class GowallaDataset(SessionDatasetv3):
    url = 'https://snap.stanford.edu/data/loc-gowalla_totalCheckins.txt.gz'

    def __init__(self, root, interval=Timedelta(days=1), n=30000):
        use_cols = [0, 1, 4]
        super().__init__(root, use_cols, interval, n)

    @property
    def raw_file_names(self) -> str:
        return 'loc-gowalla_totalCheckins.txt'

    def download(self):
        path = download_url(self.url, self.raw_dir)
        extract_gz(path, self.raw_dir)
        os.unlink(path)