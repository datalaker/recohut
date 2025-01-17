---
jupyter:
  jupytext:
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.13.7
  kernelspec:
    display_name: Python 3
    name: python3
---

```python id="JdjjuprkMSy-"
!pip install tensorflow==2.5.0
!pip install tensorflow-gpu==2.5.0
```

```python colab={"base_uri": "https://localhost:8080/"} id="-GuKHWjANGpW" executionInfo={"status": "ok", "timestamp": 1637058061296, "user_tz": -330, "elapsed": 2894, "user": {"displayName": "Sparsh Agarwal", "photoUrl": "https://lh3.googleusercontent.com/a/default-user=s64", "userId": "13037694610922482904"}} outputId="04f14de5-d50f-40a4-c03e-2b4c3b81c793"
!wget -q --show-progress https://files.grouplens.org/datasets/movielens/ml-1m.zip
!unzip ml-1m.zip
```

```python id="PruyIn0iAyRx"
import os
import pandas as pd
import numpy as np
import random
from time import time
from tqdm.notebook import tqdm
from collections import defaultdict

import tensorflow as tf
from tensorflow.keras import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.regularizers import l2
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.losses import Loss
from tensorflow.keras.layers import Layer, Dense, LayerNormalization
from tensorflow.keras.layers import Dropout, Embedding, Input, Conv1D
```

```python id="8LOSVVJUC6au" colab={"base_uri": "https://localhost:8080/"} executionInfo={"status": "ok", "timestamp": 1637058068948, "user_tz": -330, "elapsed": 5337, "user": {"displayName": "Sparsh Agarwal", "photoUrl": "https://lh3.googleusercontent.com/a/default-user=s64", "userId": "13037694610922482904"}} outputId="ba92aa67-0516-4dd4-981f-3db331fb553f"
!pip install -q watermark
%reload_ext watermark
%watermark -m -iv -u -t -d
```

```python id="9vSaa-LDB4KO"
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['CUDA_VISIBLE_DEVICES'] = '0'

file = 'ml-1m/ratings.dat'
trans_score = 1
maxlen = 200
test_neg_num = 100

embed_dim = 50
blocks = 2
num_heads = 1
ffn_hidden_unit = 64
dropout = 0.2
norm_training = True
causality = False
embed_reg = 0  # 1e-6
K = 10

learning_rate = 0.001
# epochs = 50
epochs = 10
batch_size = 512
```

```python id="6YXVIHnhA0_B"
def sparseFeature(feat, feat_num, embed_dim=4):
    """
    create dictionary for sparse feature
    :param feat: feature name
    :param feat_num: the total number of sparse features that do not repeat
    :param embed_dim: embedding dimension
    :return:
    """
    return {'feat': feat, 'feat_num': feat_num, 'embed_dim': embed_dim}
```

```python id="PDHSNwWoA3Lm"
def create_ml_1m_dataset(file, trans_score=2, embed_dim=8, maxlen=40, test_neg_num=100):
    """
    :param file: A string. dataset path.
    :param trans_score: A scalar. Greater than it is 1, and less than it is 0.
    :param embed_dim: A scalar. latent factor.
    :param maxlen: A scalar. maxlen.
    :param test_neg_num: A scalar. The number of test negative samples
    :return: user_num, item_num, train_df, test_df
    """
    print('==========Data Preprocess Start=============')
    data_df = pd.read_csv(file, sep="::", engine='python',
                          names=['user_id', 'item_id', 'label', 'Timestamp'])
    # filtering
    data_df['item_count'] = data_df.groupby('item_id')['item_id'].transform('count')
    data_df = data_df[data_df.item_count >= 5]
    # trans score
    data_df = data_df[data_df.label >= trans_score]
    # sort
    data_df = data_df.sort_values(by=['user_id', 'Timestamp'])
    # split dataset and negative sampling
    print('============Negative Sampling===============')
    train_data, val_data, test_data = defaultdict(list), defaultdict(list), defaultdict(list)
    item_id_max = data_df['item_id'].max()
    for user_id, df in tqdm(data_df[['user_id', 'item_id']].groupby('user_id')):
        pos_list = df['item_id'].tolist()

        def gen_neg():
            neg = pos_list[0]
            while neg in set(pos_list):
                neg = random.randint(1, item_id_max)
            return neg

        neg_list = [gen_neg() for i in range(len(pos_list) + test_neg_num)]
        for i in range(1, len(pos_list)):
            hist_i = pos_list[:i]
            if i == len(pos_list) - 1:
                test_data['hist'].append(hist_i)
                test_data['pos_id'].append(pos_list[i])
                test_data['neg_id'].append(neg_list[i:])
            elif i == len(pos_list) - 2:
                val_data['hist'].append(hist_i)
                val_data['pos_id'].append(pos_list[i])
                val_data['neg_id'].append(neg_list[i])
            else:
                train_data['hist'].append(hist_i)
                train_data['pos_id'].append(pos_list[i])
                train_data['neg_id'].append(neg_list[i])
    # item feature columns
    user_num, item_num = data_df['user_id'].max() + 1, data_df['item_id'].max() + 1
    item_feat_col = sparseFeature('item_id', item_num, embed_dim)
    # shuffle
    random.shuffle(train_data)
    random.shuffle(val_data)
    # padding
    print('==================Padding===================')
    train = [pad_sequences(train_data['hist'], maxlen=maxlen), np.array(train_data['pos_id']),
               np.array(train_data['neg_id'])]
    val = [pad_sequences(val_data['hist'], maxlen=maxlen), np.array(val_data['pos_id']),
             np.array(val_data['neg_id'])]
    test = [pad_sequences(test_data['hist'], maxlen=maxlen), np.array(test_data['pos_id']),
             np.array(test_data['neg_id'])]
    print('============Data Preprocess End=============')
    return item_feat_col, train, val, test
```

```python id="vxpW2xTeNRc2"
def get_angles(pos, i, d_model):
    angle_rates = 1 / np.power(10000, (2 * (i // 2)) / np.float32(d_model))
    return pos * angle_rates


def positional_encoding(seq_inputs, embed_dim):
    angle_rads = get_angles(np.arange(seq_inputs.shape[-1])[:, np.newaxis],
                            np.arange(embed_dim)[np.newaxis, :], embed_dim)
    angle_rads[:, 0::2] = np.sin(angle_rads[:, 0::2])
    angle_rads[:, 1::2] = np.cos(angle_rads[:, 1::2])

    pos_encoding = angle_rads[np.newaxis, ...]

    return tf.cast(pos_encoding, dtype=tf.float32)


def scaled_dot_product_attention(q, k, v, mask, causality=True):
    """
    Attention Mechanism
    :param q: A 3d tensor with shape of (None, seq_len, depth), depth = d_model // num_heads
    :param k: A 3d tensor with shape of (None, seq_len, depth)
    :param v: A 3d tensor with shape of (None, seq_len, depth)
    :param mask:
    :param causality: Boolean. If True, using causality, default True
    :return:
    """
    mat_qk = tf.matmul(q, k, transpose_b=True)  # (None, seq_len, seq_len)
    dk = tf.cast(k.shape[-1], dtype=tf.float32)
    # Scaled
    scaled_att_logits = mat_qk / tf.sqrt(dk)

    paddings = tf.ones_like(scaled_att_logits) * (-2 ** 32 + 1)
    outputs = tf.where(tf.equal(mask, 0), paddings, scaled_att_logits)  # (None, seq_len, seq_len)

    # Causality
    if causality:
        diag_vals = tf.ones_like(outputs)  # (None, seq_len, seq_len)
        masks = tf.linalg.LinearOperatorLowerTriangular(diag_vals).to_dense()  # (None, seq_len, seq_len)

        paddings = tf.ones_like(masks) * (-2 ** 32 + 1)
        outputs = tf.where(tf.equal(masks, 0), paddings, outputs)  # (None, seq_len, seq_len)

    # softmax
    outputs = tf.nn.softmax(logits=outputs)  # (None, seq_len, seq_len)
    outputs = tf.matmul(outputs, v)  # (None, seq_len, depth)

    return outputs


class MultiHeadAttention(Layer):
    def __init__(self, d_model, num_heads, causality=True):
        """
        Multi Head Attention Mechanism
        :param d_model: A scalar. The self-attention hidden size.
        :param num_heads: A scalar. Number of heads. If num_heads == 1, the layer is a single self-attention layer.
        :param causality: Boolean. If True, using causality, default True
        """
        super(MultiHeadAttention, self).__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.causality = causality

        self.wq = Dense(d_model, activation=None)
        self.wk = Dense(d_model, activation=None)
        self.wv = Dense(d_model, activation=None)

    def call(self, q, k, v, mask):
        q = self.wq(q)  # (None, seq_len, d_model)
        k = self.wk(k)  # (None, seq_len, d_model)
        v = self.wv(v)  # (None, seq_len, d_model)

        # split d_model into num_heads * depth, and concatenate
        q = tf.reshape(tf.concat([tf.split(q, self.num_heads, axis=2)], axis=0),
                       (-1, q.shape[1], q.shape[2] // self.num_heads))  # (None * num_heads, seq_len, d_model // num_heads)
        k = tf.reshape(tf.concat([tf.split(k, self.num_heads, axis=2)], axis=0),
                       (-1, k.shape[1], k.shape[2] // self.num_heads))  # (None * num_heads, seq_len, d_model // num_heads)
        v = tf.reshape(tf.concat([tf.split(v, self.num_heads, axis=2)], axis=0),
                       (-1, v.shape[1], v.shape[2] // self.num_heads))  # (None * num_heads, seq_len, d_model // num_heads)

        # attention
        scaled_attention = scaled_dot_product_attention(q, k, v, mask, self.causality)  # (None * num_heads, seq_len, d_model // num_heads)

        # Reshape
        outputs = tf.concat(tf.split(scaled_attention, self.num_heads, axis=0), axis=2)  # (N, seq_len, d_model)

        return outputs


class FFN(Layer):
    def __init__(self, hidden_unit, d_model):
        """
        Feed Forward Network
        :param hidden_unit: A scalar. W1
        :param d_model: A scalar. W2
        """
        super(FFN, self).__init__()
        self.conv1 = Conv1D(filters=hidden_unit, kernel_size=1, activation='relu', use_bias=True)
        self.conv2 = Conv1D(filters=d_model, kernel_size=1, activation=None, use_bias=True)

    def call(self, inputs):
        x = self.conv1(inputs)
        output = self.conv2(x)
        return output


class EncoderLayer(Layer):
    def __init__(self, d_model, num_heads=1, ffn_hidden_unit=128, dropout=0., norm_training=True, causality=True):
        """
        Encoder Layer
        :param d_model: A scalar. The self-attention hidden size.
        :param num_heads: A scalar. Number of heads.
        :param ffn_hidden_unit: A scalar. Number of hidden unit in FFN
        :param dropout: A scalar. Number of dropout.
        :param norm_training: Boolean. If True, using layer normalization, default True
        :param causality: Boolean. If True, using causality, default True
        """
        super(EncoderLayer, self).__init__()
        self.mha = MultiHeadAttention(d_model, num_heads, causality)
        self.ffn = FFN(ffn_hidden_unit, d_model)

        self.layernorm1 = LayerNormalization(epsilon=1e-6, trainable=norm_training)
        self.layernorm2 = LayerNormalization(epsilon=1e-6, trainable=norm_training)

        self.dropout1 = Dropout(dropout)
        self.dropout2 = Dropout(dropout)

    def call(self, inputs):
        x, mask = inputs
        # self-attention
        att_out = self.mha(x, x, x, mask)  # （None, seq_len, d_model)
        att_out = self.dropout1(att_out)
        # residual add
        out1 = self.layernorm1(x + att_out)
        # ffn
        ffn_out = self.ffn(out1)
        ffn_out = self.dropout2(ffn_out)
        # residual add
        out2 = self.layernorm2(out1 + ffn_out)  # (None, seq_len, d_model)
        return out2
```

```python id="jvILsUdsNRZy"
class SASRec(tf.keras.Model):
    def __init__(self, item_fea_col, blocks=1, num_heads=1, ffn_hidden_unit=128,
                 dropout=0., maxlen=40, norm_training=True, causality=False, embed_reg=1e-6):
        """
        SASRec model
        :param item_fea_col: A dict contains 'feat_name', 'feat_num' and 'embed_dim'.
        :param blocks: A scalar. The Number of blocks.
        :param num_heads: A scalar. Number of heads.
        :param ffn_hidden_unit: A scalar. Number of hidden unit in FFN
        :param dropout: A scalar. Number of dropout.
        :param maxlen: A scalar. Number of length of sequence
        :param norm_training: Boolean. If True, using layer normalization, default True
        :param causality: Boolean. If True, using causality, default True
        :param embed_reg: A scalar. The regularizer of embedding
        """
        super(SASRec, self).__init__()
        # sequence length
        self.maxlen = maxlen
        # item feature columns
        self.item_fea_col = item_fea_col
        # embed_dim
        self.embed_dim = self.item_fea_col['embed_dim']
        # d_model must be the same as embedding_dim, because of residual connection
        self.d_model = self.embed_dim
        # item embedding
        self.item_embedding = Embedding(input_dim=self.item_fea_col['feat_num'],
                                        input_length=1,
                                        output_dim=self.item_fea_col['embed_dim'],
                                        mask_zero=True,
                                        embeddings_initializer='random_uniform',
                                        embeddings_regularizer=l2(embed_reg))
        self.pos_embedding = Embedding(input_dim=self.maxlen,
                                       input_length=1,
                                       output_dim=self.embed_dim,
                                       mask_zero=False,
                                       embeddings_initializer='random_uniform',
                                       embeddings_regularizer=l2(embed_reg))
        self.dropout = Dropout(dropout)
        # attention block
        self.encoder_layer = [EncoderLayer(self.d_model, num_heads, ffn_hidden_unit,
                                           dropout, norm_training, causality) for b in range(blocks)]

    def call(self, inputs, training=None):
        # inputs
        seq_inputs, pos_inputs, neg_inputs = inputs  # (None, maxlen), (None, 1), (None, 1)
        # mask
        mask = tf.expand_dims(tf.cast(tf.not_equal(seq_inputs, 0), dtype=tf.float32), axis=-1)  # (None, maxlen, 1)
        # seq info
        seq_embed = self.item_embedding(seq_inputs)  # (None, maxlen, dim)
        # pos encoding
        # pos_encoding = positional_encoding(seq_inputs, self.embed_dim)
        pos_encoding = tf.expand_dims(self.pos_embedding(tf.range(self.maxlen)), axis=0)
        seq_embed += pos_encoding
        seq_embed = self.dropout(seq_embed)
        att_outputs = seq_embed  # (None, maxlen, dim)
        att_outputs *= mask

        # self-attention
        for block in self.encoder_layer:
            att_outputs = block([att_outputs, mask])  # (None, seq_len, dim)
            att_outputs *= mask

        # user_info = tf.reduce_mean(att_outputs, axis=1)  # (None, dim)
        user_info = tf.expand_dims(att_outputs[:, -1], axis=1)  # (None, 1, dim)
        # item info
        pos_info = self.item_embedding(pos_inputs)  # (None, 1, dim)
        neg_info = self.item_embedding(neg_inputs)  # (None, 1/100, dim)
        pos_logits = tf.reduce_sum(user_info * pos_info, axis=-1)  # (None, 1)
        neg_logits = tf.reduce_sum(user_info * neg_info, axis=-1)  # (None, 1)
        # loss
        losses = tf.reduce_mean(- tf.math.log(tf.nn.sigmoid(pos_logits)) -
                                tf.math.log(1 - tf.nn.sigmoid(neg_logits))) / 2
        self.add_loss(losses)
        logits = tf.concat([pos_logits, neg_logits], axis=-1)
        return logits

    def summary(self):
        seq_inputs = Input(shape=(self.maxlen,), dtype=tf.int32)
        pos_inputs = Input(shape=(1,), dtype=tf.int32)
        neg_inputs = Input(shape=(1,), dtype=tf.int32)
        tf.keras.Model(inputs=[seq_inputs, pos_inputs, neg_inputs],
                       outputs=self.call([seq_inputs, pos_inputs, neg_inputs])).summary()
```

```python id="jNhwtb9JN6m7"
def test_model():
    item_fea_col = {'feat': 'item_id', 'feat_num': 100, 'embed_dim': 8}
    model = SASRec(item_fea_col, num_heads=8)
    model.summary()
```

```python id="nM2p7ZIgNRW2"
def evaluate_model(model, test, K):
    """
    evaluate model
    :param model: model
    :param test: test set
    :param K: top K
    :return: hit rate, ndcg
    """
    pred_y = - model.predict(test)
    rank = pred_y.argsort().argsort()[:, 0]
    hr, ndcg = 0.0, 0.0
    for r in rank:
        if r < K:
            hr += 1
            ndcg += 1 / np.log2(r + 2)
    return hr / len(rank), ndcg / len(rank)
```

```python id="Qubt4TjBNRTY"
# ========================== Create dataset =======================
item_fea_col, train, val, test = create_ml_1m_dataset(file, trans_score, embed_dim, maxlen, test_neg_num)

# ============================Build Model==========================
mirrored_strategy = tf.distribute.MirroredStrategy()
with mirrored_strategy.scope():
    model = SASRec(item_fea_col, blocks, num_heads, ffn_hidden_unit, dropout,
                    maxlen, norm_training, causality, embed_reg)
    model.summary()
    # =========================Compile============================
    model.compile(optimizer=Adam(learning_rate=learning_rate))

results = []
for epoch in range(1, epochs + 1):
    # ===========================Fit==============================
    t1 = time()
    model.fit(
        train,
        validation_data=(val, None),
        epochs=1,
        batch_size=batch_size,
    )
    # ===========================Test==============================
    t2 = time()
    if epoch % 5 == 0:
        hit_rate, ndcg = evaluate_model(model, test, K)
        print('Iteration %d Fit [%.1f s], Evaluate [%.1f s]: HR = %.4f, NDCG = %.4f, '
                % (epoch, t2 - t1, time() - t2, hit_rate, ndcg))
        results.append([epoch + 1, t2 - t1, time() - t2, hit_rate, ndcg])
# ============================Write============================
pd.DataFrame(results, columns=['Iteration', 'fit_time', 'evaluate_time', 'hit_rate', 'ndcg']).\
    to_csv('SASRec_log_maxlen_{}_dim_{}_blocks_{}_heads_{}_K_{}_.csv'.
            format(maxlen, embed_dim, blocks, num_heads, K), index=False)
```
