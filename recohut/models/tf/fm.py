# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/models/tf/fm.ipynb (unless otherwise specified).

__all__ = ['FM_Layer', 'FM_Layer_v2', 'FM', 'FFM_Layer', 'FFM', 'DNN', 'NFM', 'AFM', 'DeepFM', 'DNN_v2', 'Linear',
           'CIN', 'xDeepFM']

# Cell
import numpy as np
import itertools

import tensorflow as tf
from tensorflow.keras import Model
from tensorflow.keras.layers import Layer, Input, ReLU, Flatten
from tensorflow.keras.layers import Dense, Embedding, Dropout
from tensorflow.keras.layers import BatchNormalization
from tensorflow.keras.regularizers import l2

# Cell
class FM_Layer(Layer):
    def __init__(self, feature_columns, k, w_reg=1e-6, v_reg=1e-6):
        """
        Factorization Machines
        :param feature_columns: A list. sparse column feature information.
        :param k: the latent vector
        :param w_reg: the regularization coefficient of parameter w
        :param v_reg: the regularization coefficient of parameter v
        """
        super(FM_Layer, self).__init__()
        self.sparse_feature_columns = feature_columns
        self.index_mapping = []
        self.feature_length = 0
        for feat in self.sparse_feature_columns:
            self.index_mapping.append(self.feature_length)
            self.feature_length += feat['feat_num']
        self.k = k
        self.w_reg = w_reg
        self.v_reg = v_reg

    def build(self, input_shape):
        self.w0 = self.add_weight(name='w0', shape=(1,),
                                  initializer=tf.zeros_initializer(),
                                  trainable=True)
        self.w = self.add_weight(name='w', shape=(self.feature_length, 1),
                                 initializer=tf.random_normal_initializer(),
                                 regularizer=l2(self.w_reg),
                                 trainable=True)
        self.V = self.add_weight(name='V', shape=(self.feature_length, self.k),
                                 initializer=tf.random_normal_initializer(),
                                 regularizer=l2(self.v_reg),
                                 trainable=True)

    def call(self, inputs, **kwargs):
        # mapping
        inputs = inputs + tf.convert_to_tensor(self.index_mapping)
        # first order
        first_order = self.w0 + tf.reduce_sum(tf.nn.embedding_lookup(self.w, inputs), axis=1)  # (batch_size, 1)
        # second order
        second_inputs = tf.nn.embedding_lookup(self.V, inputs)  # (batch_size, fields, embed_dim)
        square_sum = tf.square(tf.reduce_sum(second_inputs, axis=1, keepdims=True))  # (batch_size, 1, embed_dim)
        sum_square = tf.reduce_sum(tf.square(second_inputs), axis=1, keepdims=True)  # (batch_size, 1, embed_dim)
        second_order = 0.5 * tf.reduce_sum(square_sum - sum_square, axis=2)  # (batch_size, 1)
        # outputs
        outputs = first_order + second_order
        return outputs

# Cell
class FM_Layer_v2(Layer):
    """
    Wide part
    """
    def __init__(self, feature_length, w_reg=1e-6):
        """
        Factorization Machine
        In DeepFM, only the first order feature and second order feature intersect are included.
        :param feature_length: A scalar. The length of features.
        :param w_reg: A scalar. The regularization coefficient of parameter w.
        """
        super(FM_Layer_v2, self).__init__()
        self.feature_length = feature_length
        self.w_reg = w_reg

    def build(self, input_shape):
        self.w = self.add_weight(name='w', shape=(self.feature_length, 1),
                                 initializer='random_normal',
                                 regularizer=l2(self.w_reg),
                                 trainable=True)

    def call(self, inputs, **kwargs):
        """
        :param inputs: A dict with shape `(batch_size, {'sparse_inputs', 'embed_inputs'})`:
          sparse_inputs is 2D tensor with shape `(batch_size, sum(field_num))`
          embed_inputs is 3D tensor with shape `(batch_size, fields, embed_dim)`
        """
        sparse_inputs, embed_inputs = inputs['sparse_inputs'], inputs['embed_inputs']
        # first order
        first_order = tf.reduce_sum(tf.nn.embedding_lookup(self.w, sparse_inputs), axis=1)  # (batch_size, 1)
        # second order
        square_sum = tf.square(tf.reduce_sum(embed_inputs, axis=1, keepdims=True))  # (batch_size, 1, embed_dim)
        sum_square = tf.reduce_sum(tf.square(embed_inputs), axis=1, keepdims=True)  # (batch_size, 1, embed_dim)
        second_order = 0.5 * tf.reduce_sum(square_sum - sum_square, axis=2)  # (batch_size, 1)
        return first_order + second_order

# Cell
class FM(Model):
    def __init__(self, feature_columns, k, w_reg=1e-6, v_reg=1e-6):
        """
        Factorization Machines
        :param feature_columns: A list. sparse column feature information.
        :param k: the latent vector
        :param w_reg: the regularization coefficient of parameter w
		:param v_reg: the regularization coefficient of parameter v
        """
        super(FM, self).__init__()
        self.sparse_feature_columns = feature_columns
        self.fm = FM_Layer(feature_columns, k, w_reg, v_reg)

    def call(self, inputs, **kwargs):
        fm_outputs = self.fm(inputs)
        outputs = tf.nn.sigmoid(fm_outputs)
        return outputs

    def summary(self, **kwargs):
        sparse_inputs = Input(shape=(len(self.sparse_feature_columns),), dtype=tf.int32)
        Model(inputs=sparse_inputs, outputs=self.call(sparse_inputs)).summary()

# Cell
class FFM_Layer(Layer):
    def __init__(self, sparse_feature_columns, k, w_reg=1e-6, v_reg=1e-6):
        """
        :param dense_feature_columns: A list. sparse column feature information.
        :param k: A scalar. The latent vector
        :param w_reg: A scalar. The regularization coefficient of parameter w
		:param v_reg: A scalar. The regularization coefficient of parameter v
        """
        super(FFM_Layer, self).__init__()
        self.sparse_feature_columns = sparse_feature_columns
        self.k = k
        self.w_reg = w_reg
        self.v_reg = v_reg
        self.index_mapping = []
        self.feature_length = 0
        for feat in self.sparse_feature_columns:
            self.index_mapping.append(self.feature_length)
            self.feature_length += feat['feat_num']
        self.field_num = len(self.sparse_feature_columns)

    def build(self, input_shape):
        self.w0 = self.add_weight(name='w0', shape=(1,),
                                  initializer=tf.zeros_initializer(),
                                  trainable=True)
        self.w = self.add_weight(name='w', shape=(self.feature_length, 1),
                                 initializer='random_normal',
                                 regularizer=l2(self.w_reg),
                                 trainable=True)
        self.v = self.add_weight(name='v',
                                 shape=(self.feature_length, self.field_num, self.k),
                                 initializer='random_normal',
                                 regularizer=l2(self.v_reg),
                                 trainable=True)

    def call(self, inputs, **kwargs):
        inputs = inputs + tf.convert_to_tensor(self.index_mapping)
        # first order
        first_order = self.w0 + tf.reduce_sum(tf.nn.embedding_lookup(self.w, inputs), axis=1)  # (batch_size, 1)
        # field second order
        second_order = 0
        latent_vector = tf.reduce_sum(tf.nn.embedding_lookup(self.v, inputs), axis=1)  # (batch_size, field_num, k)
        for i in range(self.field_num):
            for j in range(i+1, self.field_num):
                second_order += tf.reduce_sum(latent_vector[:, i] * latent_vector[:, j], axis=1, keepdims=True)
        return first_order + second_order

# Cell
class FFM(Model):
    def __init__(self, feature_columns, k, w_reg=1e-6, v_reg=1e-6):
        """
        FFM architecture
        :param feature_columns: A list. sparse column feature information.
        :param k: the latent vector
        :param w_reg: the regularization coefficient of parameter w
		:param field_reg_reg: the regularization coefficient of parameter v
        """
        super(FFM, self).__init__()
        self.sparse_feature_columns = feature_columns
        self.ffm = FFM_Layer(self.sparse_feature_columns, k, w_reg, v_reg)

    def call(self, inputs, **kwargs):
        ffm_out = self.ffm(inputs)
        outputs = tf.nn.sigmoid(ffm_out)
        return outputs

    def summary(self, **kwargs):
        sparse_inputs = Input(shape=(len(self.sparse_feature_columns),), dtype=tf.int32)
        tf.keras.Model(inputs=sparse_inputs, outputs=self.call(sparse_inputs)).summary()

# Cell
class DNN(Layer):
    def __init__(self, hidden_units, activation='relu', dropout=0.):
        """Deep Neural Network
		:param hidden_units: A list. Neural network hidden units.
		:param activation: A string. Activation function of dnn.
		:param dropout: A scalar. Dropout number.
		"""
        super(DNN, self).__init__()
        self.dnn_network = [Dense(units=unit, activation=activation) for unit in hidden_units]
        self.dropout = Dropout(dropout)

    def call(self, inputs, **kwargs):
        x = inputs
        for dnn in self.dnn_network:
            x = dnn(x)
        x = self.dropout(x)
        return x

# Cell
class NFM(Model):
    def __init__(self, feature_columns, hidden_units, dnn_dropout=0., activation='relu', bn_use=True, embed_reg=1e-6):
        """
        NFM architecture
        :param feature_columns: A list. sparse column feature information.
        :param hidden_units: A list. Neural network hidden units.
        :param activation: A string. Activation function of dnn.
        :param dnn_dropout: A scalar. Dropout of dnn.
        :param bn_use: A Boolean. Use BatchNormalization or not.
        :param embed_reg: A scalar. The regularizer of embedding.
        """
        super(NFM, self).__init__()
        self.sparse_feature_columns = feature_columns
        self.embed_layers = {
            'embed_' + str(i): Embedding(input_dim=feat['feat_num'],
                                         input_length=1,
                                         output_dim=feat['embed_dim'],
                                         embeddings_initializer='random_normal',
                                         embeddings_regularizer=l2(embed_reg))
            for i, feat in enumerate(self.sparse_feature_columns)
        }
        self.bn = BatchNormalization()
        self.bn_use = bn_use
        self.dnn_network = DNN(hidden_units, activation, dnn_dropout)
        self.dense = Dense(1, activation=None)

    def call(self, inputs):
        # Inputs layer
        sparse_inputs = inputs
        # Embedding layer
        sparse_embed = [self.embed_layers['embed_{}'.format(i)](sparse_inputs[:, i])
                 for i in range(sparse_inputs.shape[1])]
        sparse_embed = tf.transpose(tf.convert_to_tensor(sparse_embed), [1, 0, 2])  # (None, filed_num, embed_dim)
        # Bi-Interaction Layer
        sparse_embed = 0.5 * (tf.pow(tf.reduce_sum(sparse_embed, axis=1), 2) -
                       tf.reduce_sum(tf.pow(sparse_embed, 2), axis=1))  # (None, embed_dim)
        # Concat
        x = sparse_embed
        # BatchNormalization
        x = self.bn(x, training=self.bn_use)
        # Hidden Layers
        x = self.dnn_network(x)
        outputs = tf.nn.sigmoid(self.dense(x))
        return outputs

    def summary(self):
        sparse_inputs = Input(shape=(len(self.sparse_feature_columns),), dtype=tf.int32)
        tf.keras.Model(inputs=sparse_inputs, outputs=self.call(sparse_inputs)).summary()

# Cell
class AFM(Model):
    def __init__(self, feature_columns, mode, att_vector=8, activation='relu', dropout=0.5, embed_reg=1e-6):
        """
        AFM
        :param feature_columns: A list. sparse column feature information.
        :param mode: A string. 'max'(MAX Pooling) or 'avg'(Average Pooling) or 'att'(Attention)
        :param att_vector: A scalar. attention vector.
        :param activation: A string. Activation function of attention.
        :param dropout: A scalar. Dropout.
        :param embed_reg: A scalar. the regularizer of embedding
        """
        super(AFM, self).__init__()
        self.sparse_feature_columns = feature_columns
        self.mode = mode
        self.embed_layers = {
            'embed_' + str(i): Embedding(input_dim=feat['feat_num'],
                                         input_length=1,
                                         output_dim=feat['embed_dim'],
                                         embeddings_initializer='random_uniform',
                                         embeddings_regularizer=l2(embed_reg))
            for i, feat in enumerate(self.sparse_feature_columns)
        }
        if self.mode == 'att':
            self.attention_W = Dense(units=att_vector, activation=activation, use_bias=True)
            self.attention_dense = Dense(units=1, activation=None)
        self.dropout = Dropout(dropout)
        self.dense = Dense(units=1, activation=None)

    def call(self, inputs):
        # Input Layer
        sparse_inputs = inputs
        # Embedding Layer
        embed = [self.embed_layers['embed_{}'.format(i)](sparse_inputs[:, i]) for i in range(sparse_inputs.shape[1])]
        embed = tf.transpose(tf.convert_to_tensor(embed), perm=[1, 0, 2])  # (None, len(sparse_inputs), embed_dim)
        # Pair-wise Interaction Layer
        row = []
        col = []
        for r, c in itertools.combinations(range(len(self.sparse_feature_columns)), 2):
            row.append(r)
            col.append(c)
        p = tf.gather(embed, row, axis=1)  # (None, (len(sparse) * len(sparse) - 1) / 2, k)
        q = tf.gather(embed, col, axis=1)  # (None, (len(sparse) * len(sparse) - 1) / 2, k)
        bi_interaction = p * q  # (None, (len(sparse) * len(sparse) - 1) / 2, k)
        # mode
        if self.mode == 'max':
            # MaxPooling Layer
            x = tf.reduce_sum(bi_interaction, axis=1)   # (None, k)
        elif self.mode == 'avg':
            # AvgPooling Layer
            x = tf.reduce_mean(bi_interaction, axis=1)  # (None, k)
        else:
            # Attention Layer
            x = self.attention(bi_interaction)  # (None, k)
        # Output Layer
        outputs = tf.nn.sigmoid(self.dense(x))

        return outputs

    def summary(self):
        sparse_inputs = Input(shape=(len(self.sparse_feature_columns),), dtype=tf.int32)
        Model(inputs=sparse_inputs, outputs=self.call(sparse_inputs)).summary()

    def attention(self, bi_interaction):
        a = self.attention_W(bi_interaction)  # (None, (len(sparse) * len(sparse) - 1) / 2, t)
        a = self.attention_dense(a)  # (None, (len(sparse) * len(sparse) - 1) / 2, 1)
        a_score = tf.nn.softmax(a, axis=1)  # (None, (len(sparse) * len(sparse) - 1) / 2, 1)
        outputs = tf.reduce_sum(bi_interaction * a_score, axis=1)  # (None, embed_dim)
        return outputs

# Cell
class DeepFM(Model):
	def __init__(self, feature_columns, hidden_units=(200, 200, 200), dnn_dropout=0.,
				 activation='relu', fm_w_reg=1e-6, embed_reg=1e-6):
		"""
		DeepFM
		:param feature_columns: A list. sparse column feature information.
		:param hidden_units: A list. A list of dnn hidden units.
		:param dnn_dropout: A scalar. Dropout of dnn.
		:param activation: A string. Activation function of dnn.
		:param fm_w_reg: A scalar. The regularizer of w in fm.
		:param embed_reg: A scalar. The regularizer of embedding.
		"""
		super(DeepFM, self).__init__()
		self.sparse_feature_columns = feature_columns
		self.embed_layers = {
			'embed_' + str(i): Embedding(input_dim=feat['feat_num'],
										 input_length=1,
										 output_dim=feat['embed_dim'],
										 embeddings_initializer='random_normal',
										 embeddings_regularizer=l2(embed_reg))
			for i, feat in enumerate(self.sparse_feature_columns)
		}
		self.index_mapping = []
		self.feature_length = 0
		for feat in self.sparse_feature_columns:
			self.index_mapping.append(self.feature_length)
			self.feature_length += feat['feat_num']
		self.embed_dim = self.sparse_feature_columns[0]['embed_dim']  # all sparse features have the same embed_dim
		self.fm = FM_Layer_v2(self.feature_length, fm_w_reg)
		self.dnn = DNN(hidden_units, activation, dnn_dropout)
		self.dense = Dense(1, activation=None)

	def call(self, inputs, **kwargs):
		sparse_inputs = inputs
		# embedding
		sparse_embed = tf.concat([self.embed_layers['embed_{}'.format(i)](sparse_inputs[:, i])
                                  for i in range(sparse_inputs.shape[1])], axis=-1)  # (batch_size, embed_dim * fields)
		# wide
		sparse_inputs = sparse_inputs + tf.convert_to_tensor(self.index_mapping)
		wide_inputs = {'sparse_inputs': sparse_inputs,
					   'embed_inputs': tf.reshape(sparse_embed, shape=(-1, sparse_inputs.shape[1], self.embed_dim))}
		wide_outputs = self.fm(wide_inputs)  # (batch_size, 1)
		# deep
		deep_outputs = self.dnn(sparse_embed)
		deep_outputs = self.dense(deep_outputs)  # (batch_size, 1)
		# outputs
		outputs = tf.nn.sigmoid(tf.add(wide_outputs, deep_outputs))
		return outputs

	def summary(self):
		sparse_inputs = Input(shape=(len(self.sparse_feature_columns),), dtype=tf.int32)
		Model(inputs=sparse_inputs, outputs=self.call(sparse_inputs)).summary()

# Cell
class DNN_v2(Layer):
    def __init__(self, hidden_units, dnn_dropout=0., dnn_activation='relu'):
        """DNN
        :param hidden_units: A list. list of hidden layer units's numbers.
        :param dnn_dropout: A scalar. dropout number.
        :param dnn_activation: A string. activation function.
        """
        super(DNN_v2, self).__init__()
        self.dnn_network = [Dense(units=unit, activation=dnn_activation) for unit in hidden_units]
        self.dropout = Dropout(dnn_dropout)

    def call(self, inputs, **kwargs):
        x = inputs
        for dnn in self.dnn_network:
            x = dnn(x)
        x = self.dropout(x)
        return x

# Cell
class Linear(Layer):
    def __init__(self, feature_length, w_reg=1e-6):
        """
        Linear Part
        :param feature_length: A scalar. The length of features.
        :param w_reg: A scalar. The regularization coefficient of parameter w.
        """
        super(Linear, self).__init__()
        self.feature_length = feature_length
        self.w_reg = w_reg

    def build(self, input_shape):
        self.w = self.add_weight(name="w",
                                 shape=(self.feature_length, 1),
                                 regularizer=l2(self.w_reg),
                                 trainable=True)

    def call(self, inputs, **kwargs):
        result = tf.reduce_sum(tf.nn.embedding_lookup(self.w, inputs), axis=1)  # (batch_size, 1)
        return result

# Cell
class CIN(Layer):
    def __init__(self, cin_size, l2_reg=1e-4):
        """CIN
        :param cin_size: A list. [H_1, H_2 ,..., H_k], a list of the number of layers
        :param l2_reg: A scalar. L2 regularization.
        """
        super(CIN, self).__init__()
        self.cin_size = cin_size
        self.l2_reg = l2_reg

    def build(self, input_shape):
        # get the number of embedding fields
        self.embedding_nums = input_shape[1]
        # a list of the number of CIN
        self.field_nums = [self.embedding_nums] + self.cin_size
        # filters
        self.cin_W = {
            'CIN_W_' + str(i): self.add_weight(
                name='CIN_W_' + str(i),
                shape=(1, self.field_nums[0] * self.field_nums[i], self.field_nums[i + 1]),
                initializer='random_normal',
                regularizer=l2(self.l2_reg),
                trainable=True)
            for i in range(len(self.field_nums) - 1)
        }

    def call(self, inputs, **kwargs):
        dim = inputs.shape[-1]
        hidden_layers_results = [inputs]
        # split dimension 2 for convenient calculation
        split_X_0 = tf.split(hidden_layers_results[0], dim, 2)  # dim * (None, field_nums[0], 1)
        for idx, size in enumerate(self.cin_size):
            split_X_K = tf.split(hidden_layers_results[-1], dim, 2)  # dim * (None, filed_nums[i], 1)

            result_1 = tf.matmul(split_X_0, split_X_K, transpose_b=True)  # (dim, None, field_nums[0], field_nums[i])

            result_2 = tf.reshape(result_1, shape=[dim, -1, self.embedding_nums * self.field_nums[idx]])

            result_3 = tf.transpose(result_2, perm=[1, 0, 2])  # (None, dim, field_nums[0] * field_nums[i])

            result_4 = tf.nn.conv1d(input=result_3, filters=self.cin_W['CIN_W_' + str(idx)], stride=1,
                                    padding='VALID')

            result_5 = tf.transpose(result_4, perm=[0, 2, 1])  # (None, field_num[i+1], dim)

            hidden_layers_results.append(result_5)

        final_results = hidden_layers_results[1:]
        result = tf.concat(final_results, axis=1)  # (None, H_1 + ... + H_K, dim)
        result = tf.reduce_sum(result,  axis=-1)  # (None, dim)

        return result

# Cell
class xDeepFM(Model):
    def __init__(self, feature_columns, hidden_units, cin_size, dnn_dropout=0, dnn_activation='relu',
                 embed_reg=1e-6, cin_reg=1e-6, w_reg=1e-6):
        """
        xDeepFM
        :param feature_columns: A list. sparse column feature information.
        :param hidden_units: A list. a list of dnn hidden units.
        :param cin_size: A list. a list of the number of CIN layers.
        :param dnn_dropout: A scalar. dropout of dnn.
        :param dnn_activation: A string. activation function of dnn.
        :param embed_reg: A scalar. The regularizer of embedding.
        :param cin_reg: A scalar. The regularizer of cin.
        :param w_reg: A scalar. The regularizer of Linear.
        """
        super(xDeepFM, self).__init__()
        self.sparse_feature_columns = feature_columns
        self.embed_dim = self.sparse_feature_columns[0]['embed_dim']
        self.embed_layers = {
            'embed_' + str(i): Embedding(input_dim=feat['feat_num'],
                                         input_length=1,
                                         output_dim=feat['embed_dim'],
                                         embeddings_initializer='random_normal',
                                         embeddings_regularizer=l2(embed_reg))
            for i, feat in enumerate(self.sparse_feature_columns)
        }
        self.index_mapping = []
        self.feature_length = 0
        for feat in self.sparse_feature_columns:
            self.index_mapping.append(self.feature_length)
            self.feature_length += feat['feat_num']
        self.linear = Linear(self.feature_length, w_reg)
        self.cin = CIN(cin_size=cin_size, l2_reg=cin_reg)
        self.dnn = DNN_v2(hidden_units=hidden_units, dnn_dropout=dnn_dropout, dnn_activation=dnn_activation)
        self.cin_dense = Dense(1)
        self.dnn_dense = Dense(1)
        self.bias = self.add_weight(name='bias', shape=(1, ), initializer=tf.zeros_initializer())

    def call(self, inputs, **kwargs):
        # Linear
        linear_inputs = inputs + tf.convert_to_tensor(self.index_mapping)
        linear_out = self.linear(linear_inputs)  # (batch_size, 1)
        # cin
        embed = [self.embed_layers['embed_{}'.format(i)](inputs[:, i]) for i in range(inputs.shape[1])]
        embed_matrix = tf.transpose(tf.convert_to_tensor(embed), [1, 0, 2])
        cin_out = self.cin(embed_matrix)  # (batch_size, dim)
        cin_out = self.cin_dense(cin_out)  # (batch_size, 1)
        # dnn
        embed_vector = tf.reshape(embed_matrix, shape=(-1, embed_matrix.shape[1] * embed_matrix.shape[2]))
        dnn_out = self.dnn(embed_vector)
        dnn_out = self.dnn_dense(dnn_out)  # (batch_size, 1))
        # output
        output = tf.nn.sigmoid(linear_out + cin_out + dnn_out + self.bias)
        return output

    def summary(self):
        sparse_inputs = Input(shape=(len(self.sparse_feature_columns),), dtype=tf.int32)
        Model(inputs=sparse_inputs, outputs=self.call(sparse_inputs)).summary()