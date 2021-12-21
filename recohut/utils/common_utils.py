# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/utils/common_utils.ipynb (unless otherwise specified).

__all__ = ['wget_download', 'download_url', 'extract_tar', 'extract_zip', 'extract_bz2', 'extract_gz']

# Cell
import sys
import ssl
import os.path as osp
from six.moves import urllib
import errno
import tarfile
import zipfile
import bz2
import gzip

# Internal Cell
def makedirs(path):
    try:
        os.makedirs(osp.expanduser(osp.normpath(path)))
    except OSError as e:
        if e.errno != errno.EEXIST and osp.isdir(path):
            raise e

# Cell
def wget_download(url, savepath):
    import wget
    wget.download(url, str(savepath))

# Cell
def download_url(url: str, folder: str, log: bool = True):
    r"""Downloads the content of an URL to a specific folder.
    Args:
        url (string): The url.
        folder (string): The folder.
        log (bool, optional): If :obj:`False`, will not print anything to the
            console. (default: :obj:`True`)
    """

    filename = url.rpartition('/')[2]
    filename = filename if filename[0] == '?' else filename.split('?')[0]
    path = osp.join(folder, filename)

    if osp.exists(path):  # pragma: no cover
        if log:
            print(f'Using existing file {filename}', file=sys.stderr)
        return path

    if log:
        print(f'Downloading {url}', file=sys.stderr)

    makedirs(folder)

    context = ssl._create_unverified_context()
    data = urllib.request.urlopen(url, context=context)

    with open(path, 'wb') as f:
        f.write(data.read())

    return path

# Internal Cell
def maybe_log(path, log=True):
    if log:
        print(f'Extracting {path}', file=sys.stderr)

# Cell
def extract_tar(path: str, folder: str, mode: str = 'r:gz', log: bool = True):
    r"""Extracts a tar archive to a specific folder.
    Args:
        path (string): The path to the tar archive.
        folder (string): The folder.
        mode (string, optional): The compression mode. (default: :obj:`"r:gz"`)
        log (bool, optional): If :obj:`False`, will not print anything to the
            console. (default: :obj:`True`)
    """
    maybe_log(path, log)
    with tarfile.open(path, mode) as f:
        f.extractall(folder)

# Cell
def extract_zip(path: str, folder: str, log: bool = True):
    r"""Extracts a zip archive to a specific folder.
    Args:
        path (string): The path to the tar archive.
        folder (string): The folder.
        log (bool, optional): If :obj:`False`, will not print anything to the
            console. (default: :obj:`True`)
    """
    maybe_log(path, log)
    with zipfile.ZipFile(path, 'r') as f:
        f.extractall(folder)

# Cell
def extract_bz2(path: str, folder: str, log: bool = True):
    r"""Extracts a bz2 archive to a specific folder.
    Args:
        path (string): The path to the tar archive.
        folder (string): The folder.
        log (bool, optional): If :obj:`False`, will not print anything to the
            console. (default: :obj:`True`)
    """
    maybe_log(path, log)
    path = osp.abspath(path)
    with bz2.open(path, 'r') as r:
        with open(osp.join(folder, '.'.join(path.split('.')[:-1])), 'wb') as w:
            w.write(r.read())

# Cell
def extract_gz(path: str, folder: str, log: bool = True):
    r"""Extracts a gz archive to a specific folder.
    Args:
        path (string): The path to the tar archive.
        folder (string): The folder.
        log (bool, optional): If :obj:`False`, will not print anything to the
            console. (default: :obj:`True`)
    """
    maybe_log(path, log)
    path = osp.abspath(path)
    with gzip.open(path, 'r') as r:
        with open(osp.join(folder, '.'.join(path.split('.')[:-1])), 'wb') as w:
            w.write(r.read())