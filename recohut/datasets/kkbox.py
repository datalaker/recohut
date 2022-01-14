# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/datasets/datasets.kkbox.ipynb (unless otherwise specified).

__all__ = ['KKBoxDataset', 'KKBoxDataModule']

# Cell
from .bases.ctr import *
from ..utils.common_utils import download_url, extract_zip

import pandas as pd
import numpy as np
import os
from datetime import datetime, date

# Cell
class KKBoxDataset(CTRDataset):

    feature_cols = [
                    {'name': ["msno","song_id","source_system_tab","source_screen_name","source_type","city","gender",
                  "registered_via","language"], 'active': True, 'dtype': 'str', 'type': 'categorical'},
                    {'name': 'genre_ids', 'active': True, 'dtype': 'str', 'type': 'sequence', 'max_len': 3},
                    {'name': 'artist_name', 'active': True, 'dtype': 'str', 'type': 'sequence', 'max_len': 3},
                    {'name': 'isrc', 'active': True, 'dtype': 'str', 'type': 'categorical', 'preprocess': 'extract_country_code'},
                    {'name': 'bd', 'active': True, 'dtype': 'str', 'type': 'categorical', 'preprocess': 'bucketize_age'}]

    label_col = {'name': 'label', 'dtype': float}

    url = "https://zenodo.org/record/5700987/files/KKBox_x1.zip"

    @property
    def raw_file_names(self):
        return ['train.csv',
                'valid.csv',
                'test.csv']

    def download(self):
        path = download_url(self.url, self.raw_dir)
        extract_zip(path, self.raw_dir)
        os.unlink(path)

    def extract_country_code(self, df, col_name):
        return df[col_name].apply(lambda isrc: isrc[0:2] if not pd.isnull(isrc) else "")

    def bucketize_age(self, df, col_name):
        def _bucketize(age):
            if pd.isnull(age):
                return ""
            else:
                age = float(age)
                if age < 1 or age > 95:
                    return ""
                elif age <= 10:
                    return "1"
                elif age <=20:
                    return "2"
                elif age <=30:
                    return "3"
                elif age <=40:
                    return "4"
                elif age <=50:
                    return "5"
                elif age <=60:
                    return "6"
                else:
                    return "7"
        return df[col_name].apply(_bucketize)

# Cell
class KKBoxDataModule(CTRDataModule):
    dataset_cls = KKBoxDataset