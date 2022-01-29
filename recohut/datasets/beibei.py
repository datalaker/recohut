# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/datasets/datasets.beibei.ipynb (unless otherwise specified).

__all__ = ['BeibeiDataset']

# Cell
import numpy as np
import scipy.sparse as sp
import pickle

from .bases.common import Dataset
from ..utils.common_utils import *

# Cell
class BeibeiDataset(Dataset):
    def __init__(self, data_dir):
        self.behs = ['pv', 'cart', 'buy']
        super().__init__(data_dir)

        self._process()

    @property
    def raw_file_names(self):
        return ['trn_buy','trn_cart','trn_pv','tst_int']

    @property
    def processed_file_names(self):
        return 'data.zip'

    def download(self):
        urls = ['https://github.com/RecoHut-Datasets/beibei/raw/v1/trn_buy',
                'https://github.com/RecoHut-Datasets/beibei/raw/v1/trn_cart',
                'https://github.com/RecoHut-Datasets/beibei/raw/v1/trn_pv',
                'https://github.com/RecoHut-Datasets/beibei/raw/v1/tst_int']
        for url in urls:
            _ = download_url(url, self.raw_dir)

    def process(self):
        trnMats = list()
        for path in self.raw_paths[:3]:
            with open(path, 'rb') as fs:
                mat = (pickle.load(fs) != 0).astype(np.float32)
            trnMats.append(mat)
        # test set
        path = self.raw_paths[-1]
        with open(path, 'rb') as fs:
            tstInt = np.array(pickle.load(fs))
        tstStat = (tstInt != None)
        tstUsrs = np.reshape(np.argwhere(tstStat != False), [-1])
        self.trnMats = trnMats
        self.tstInt = tstInt
        self.tstUsrs = tstUsrs
        self.user, self.item = self.trnMats[0].shape
        self.behNum = len(self.behs)

        adj = 0
        for i in range(self.behNum):
            adj = adj + self.trnMats[i]
        adj = (adj != 0).astype(np.float32)
        self.labelP = np.squeeze(np.array(np.sum(adj, axis=0)))
        tpadj = self.transpose(adj)
        adjNorm = np.reshape(np.array(np.sum(adj, axis=1)), [-1])
        tpadjNorm = np.reshape(np.array(np.sum(tpadj, axis=1)), [-1])
        for i in range(adj.shape[0]):
            for j in range(adj.indptr[i], adj.indptr[i+1]):
                adj.data[j] /= adjNorm[i]
        for i in range(tpadj.shape[0]):
            for j in range(tpadj.indptr[i], tpadj.indptr[i+1]):
                tpadj.data[j] /= tpadjNorm[i]
        self.adj = adj
        self.tpadj = tpadj

    @staticmethod
    def transpose(mat):
        coomat = sp.coo_matrix(mat)
        return sp.csr_matrix(coomat.transpose())

    @staticmethod
    def make_mask(nodes, size):
        mask = np.ones(size)
        if not nodes is None:
            mask[nodes] = 0.0
        return mask

    @staticmethod
    def update_bdgt(adj, nodes):
        if nodes is None:
            return 0
        tembat = 1000
        ret = 0
        for i in range(int(np.ceil(len(nodes) / tembat))):
            st = tembat * i
            ed = min((i+1) * tembat, len(nodes))
            temNodes = nodes[st: ed]
            ret += np.sum(adj[temNodes], axis=0)
        return ret

    @staticmethod
    def sample(budget, mask, sampNum):
        score = (mask * np.reshape(np.array(budget), [-1])) ** 2
        norm = np.sum(score)
        if norm == 0:
            return np.random.choice(len(score), 1), sampNum - 1
        score = list(score / norm)
        arrScore = np.array(score)
        posNum = np.sum(np.array(score)!=0)
        if posNum < sampNum:
            pckNodes1 = np.squeeze(np.argwhere(arrScore!=0))
            # pckNodes2 = np.random.choice(np.squeeze(np.argwhere(arrScore==0.0)), min(len(score) - posNum, sampNum - posNum), replace=False)
            # pckNodes = np.concatenate([pckNodes1, pckNodes2], axis=0)
            pckNodes = pckNodes1
        else:
            pckNodes = np.random.choice(len(score), sampNum, p=score, replace=False)
        return pckNodes, max(sampNum - posNum, 0)

    @staticmethod
    def transToLsts(mat, mask=False, norm=False):
        shape = [mat.shape[0], mat.shape[1]]
        coomat = sp.coo_matrix(mat)
        indices = np.array(list(map(list, zip(coomat.row, coomat.col))), dtype=np.int32)
        data = coomat.data.astype(np.float32)

        if norm:
            rowD = np.squeeze(np.array(1 / (np.sqrt(np.sum(mat, axis=1) + 1e-8) + 1e-8)))
            colD = np.squeeze(np.array(1 / (np.sqrt(np.sum(mat, axis=0) + 1e-8) + 1e-8)))
            for i in range(len(data)):
                row = indices[i, 0]
                col = indices[i, 1]
                data[i] = data[i] * rowD[row] * colD[col]
        # half mask
        if mask:
            spMask = (np.random.uniform(size=data.shape) > 0.5) * 1.0
            data = data * spMask

        if indices.shape[0] == 0:
            indices = np.array([[0, 0]], dtype=np.int32)
            data = np.array([0.0], np.float32)
        return indices, data, shape

    def construct_data(self, adjs, usrs, itms):
        pckAdjs = []
        pckTpAdjs = []
        for i in range(len(adjs)):
            pckU = adjs[i][usrs]
            tpPckI = self.transpose(pckU)[itms]
            pckTpAdjs.append(tpPckI)
            pckAdjs.append(self.transpose(tpPckI))
        return pckAdjs, pckTpAdjs, usrs, itms

    def sample_large_graph(self, pckUsrs, pckItms=None, sampDepth=2, sampNum=1e3, preSamp=False):
        adj = self.adj
        tpadj = self.tpadj
        usrMask = self.make_mask(pckUsrs, adj.shape[0])
        itmMask = self.make_mask(pckItms, adj.shape[1])
        itmBdgt = self.update_bdgt(adj, pckUsrs)
        if pckItms is None:
            pckItms, _ = self.sample(itmBdgt, itmMask, len(pckUsrs))
            itmMask = itmMask * self.make_mask(pckItms, adj.shape[1])
        usrBdgt = self.update_bdgt(tpadj, pckItms)
        uSampRes = 0
        iSampRes = 0
        for i in range(sampDepth + 1):
            uSamp = uSampRes + (sampNum if i < sampDepth else 0)
            iSamp = iSampRes + (sampNum if i < sampDepth else 0)
            newUsrs, uSampRes = self.sample(usrBdgt, usrMask, uSamp)
            usrMask = usrMask * self.make_mask(newUsrs, adj.shape[0])
            newItms, iSampRes = self.sample(itmBdgt, itmMask, iSamp)
            itmMask = itmMask * self.make_mask(newItms, adj.shape[1])
            if i == sampDepth or i == sampDepth and uSampRes == 0 and iSampRes == 0:
                break
            usrBdgt += self.update_bdgt(tpadj, newItms)
            itmBdgt += self.update_bdgt(adj, newUsrs)
        usrs = np.reshape(np.argwhere(usrMask==0), [-1])
        itms = np.reshape(np.argwhere(itmMask==0), [-1])
        return self.construct_data(usrs, itms)