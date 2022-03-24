# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/visualization/visualization.eda.ipynb (unless otherwise specified).

__all__ = ['plot_sparse']

# Cell
import pandas as pd
import matplotlib.pyplot as plt

# Cell
def plot_sparse(cat_lst, tgt_lst):
    _df = pd.DataFrame.from_dict({
        'cat':cat_lst,
        'tgt':tgt_lst,
    })
    stats = _df.groupby('cat').agg(['count','mean'])
    stats = stats.reset_index()
    stats.columns = ['cat', 'count','mean']
    stats = stats.sort_values('count', ascending=False)
    fig, ax1 = plt.subplots(figsize=(15,4))
    ax2 = ax1.twinx()
    ax1.bar(stats['cat'].astype(str).values[0:20], stats['count'].values[0:20])
    ax1.set_xticklabels(stats['cat'].astype(str).values[0:20], rotation='vertical')
    ax2.plot(stats['mean'].values[0:20], color='red')
    ax2.set_ylim(0,1)
    ax2.set_ylabel('Mean Target')
    ax1.set_ylabel('Frequency')
    ax1.set_xlabel('Category')