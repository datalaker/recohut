# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/models/models.xdeepfm.ipynb (unless otherwise specified).

__all__ = ['xDeepFM', 'CompressedInteractionNetwork', 'xDeepFM_v2']

# Cell
import torch
from torch import nn

from .layers.embedding import EmbeddingLayer
from .layers.common import MLP_Layer, LR_Layer
from .layers.interaction import CompressedInteractionNet

from .bases.ctr import CTRModel

# Cell
class xDeepFM(CTRModel):
    def __init__(self,
                 feature_map,
                 model_id="xDeepFM",
                 task="binary_classification",
                 learning_rate=1e-3,
                 embedding_initializer="torch.nn.init.normal_(std=1e-4)",
                 embedding_dim=10,
                 dnn_hidden_units=[64, 64, 64],
                 dnn_activations="ReLU",
                 cin_layer_units=[16, 16, 16],
                 net_dropout=0,
                 batch_norm=False,
                 **kwargs):
        super(xDeepFM, self).__init__(feature_map,
                                           model_id=model_id,
                                           **kwargs)
        self.embedding_layer = EmbeddingLayer(feature_map, embedding_dim)
        input_dim = feature_map.num_fields * embedding_dim
        self.dnn = MLP_Layer(input_dim=input_dim,
                             output_dim=1,
                             hidden_units=dnn_hidden_units,
                             hidden_activations=dnn_activations,
                             output_activation=None,
                             dropout_rates=net_dropout,
                             batch_norm=batch_norm,
                             use_bias=True) \
                   if dnn_hidden_units else None # in case of only CIN used
        self.lr_layer = LR_Layer(feature_map, output_activation=None, use_bias=False)
        self.cin = CompressedInteractionNet(feature_map.num_fields, cin_layer_units, output_dim=1)
        self.output_activation = self.get_final_activation(task)
        self.init_weights(embedding_initializer=embedding_initializer)

    def forward(self, inputs):
        feature_emb = self.embedding_layer(inputs) # list of b x embedding_dim
        lr_logit = self.lr_layer(inputs)
        cin_logit = self.cin(feature_emb)
        if self.dnn is not None:
            dnn_logit = self.dnn(feature_emb.flatten(start_dim=1))
            y_pred = lr_logit + cin_logit + dnn_logit # LR + CIN + DNN
        else:
            y_pred = lr_logit + cin_logit # only LR + CIN
        if self.output_activation is not None:
            y_pred = self.output_activation(y_pred)
        return y_pred

# Cell
import torch

from .layers.common import FeaturesEmbedding, FeaturesLinear, MultiLayerPerceptron

# Cell
class CompressedInteractionNetwork(torch.nn.Module):

    def __init__(self, input_dim, cross_layer_sizes, split_half=True):
        super().__init__()
        self.num_layers = len(cross_layer_sizes)
        self.split_half = split_half
        self.conv_layers = torch.nn.ModuleList()
        prev_dim, fc_input_dim = input_dim, 0
        for i in range(self.num_layers):
            cross_layer_size = cross_layer_sizes[i]
            self.conv_layers.append(torch.nn.Conv1d(input_dim * prev_dim, cross_layer_size, 1,
                                                    stride=1, dilation=1, bias=True))
            if self.split_half and i != self.num_layers - 1:
                cross_layer_size //= 2
            prev_dim = cross_layer_size
            fc_input_dim += prev_dim
        self.fc = torch.nn.Linear(fc_input_dim, 1)

    def forward(self, x):
        """
        :param x: Float tensor of size ``(batch_size, num_fields, embed_dim)``
        """
        xs = list()
        x0, h = x.unsqueeze(2), x
        for i in range(self.num_layers):
            x = x0 * h.unsqueeze(1)
            batch_size, f0_dim, fin_dim, embed_dim = x.shape
            x = x.view(batch_size, f0_dim * fin_dim, embed_dim)
            x = F.relu(self.conv_layers[i](x))
            if self.split_half and i != self.num_layers - 1:
                x, h = torch.split(x, x.shape[1] // 2, dim=1)
            else:
                h = x
            xs.append(x)
        return self.fc(torch.sum(torch.cat(xs, dim=1), 2))


class xDeepFM_v2(torch.nn.Module):
    """
    A pytorch implementation of xDeepFM.
    Reference:
        J Lian, et al. xDeepFM: Combining Explicit and Implicit Feature Interactions for Recommender Systems, 2018.
    """

    def __init__(self, field_dims, embed_dim, mlp_dims, dropout, cross_layer_sizes, split_half=True):
        super().__init__()
        self.embedding = FeaturesEmbedding(field_dims, embed_dim)
        self.embed_output_dim = len(field_dims) * embed_dim
        self.cin = CompressedInteractionNetwork(len(field_dims), cross_layer_sizes, split_half)
        self.mlp = MultiLayerPerceptron(self.embed_output_dim, mlp_dims, dropout)
        self.linear = FeaturesLinear(field_dims)

    def forward(self, x):
        """
        :param x: Long tensor of size ``(batch_size, num_fields)``
        """
        embed_x = self.embedding(x)
        x = self.linear(x) + self.cin(embed_x) + self.mlp(embed_x.view(-1, self.embed_output_dim))
        return torch.sigmoid(x.squeeze(1))