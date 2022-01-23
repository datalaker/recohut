# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/models/models.autoint.ipynb (unless otherwise specified).

__all__ = ['AutoInt', 'AutoInt_v2']

# Cell
import torch
from torch import nn

from .layers.embedding import EmbeddingLayer
from .layers.common import MLP_Layer, LR_Layer
from .layers.attention import MultiHeadSelfAttention

from .bases.ctr import CTRModel

# Cell
class AutoInt(CTRModel):
    def __init__(self,
                 feature_map,
                 model_id="AutoInt",
                 task="binary_classification",
                 learning_rate=1e-3,
                 embedding_initializer="torch.nn.init.normal_(std=1e-4)",
                 embedding_dim=10,
                 dnn_hidden_units=[64, 64, 64],
                 dnn_activations="ReLU",
                 attention_layers=2,
                 num_heads=1,
                 attention_dim=8,
                 net_dropout=0,
                 batch_norm=False,
                 layer_norm=False,
                 use_scale=False,
                 use_wide=False,
                 use_residual=True,
                 **kwargs):
        super(AutoInt, self).__init__(feature_map,
                                           model_id=model_id,
                                           **kwargs)
        self.embedding_layer = EmbeddingLayer(feature_map, embedding_dim)
        self.lr_layer = LR_Layer(feature_map, output_activation=None, use_bias=False) \
                        if use_wide else None
        self.dnn = MLP_Layer(input_dim=embedding_dim * feature_map.num_fields,
                             output_dim=1,
                             hidden_units=dnn_hidden_units,
                             hidden_activations=dnn_activations,
                             output_activation=None,
                             dropout_rates=net_dropout,
                             batch_norm=batch_norm,
                             use_bias=True) \
                   if dnn_hidden_units else None # in case no DNN used
        self.self_attention = nn.Sequential(
            *[MultiHeadSelfAttention(embedding_dim if i == 0 else num_heads * attention_dim,
                                    attention_dim=attention_dim,
                                    num_heads=num_heads,
                                    dropout_rate=net_dropout,
                                    use_residual=use_residual,
                                    use_scale=use_scale,
                                    layer_norm=layer_norm,
                                    align_to="output")
             for i in range(attention_layers)])
        self.fc = nn.Linear(feature_map.num_fields * attention_dim * num_heads, 1)
        self.output_activation = self.get_final_activation(task)
        self.init_weights(embedding_initializer=embedding_initializer)

    def forward(self, inputs):
        feature_emb = self.embedding_layer(inputs)
        attention_out = self.self_attention(feature_emb)
        attention_out = torch.flatten(attention_out, start_dim=1)
        y_pred = self.fc(attention_out)
        if self.dnn is not None:
            y_pred += self.dnn(feature_emb.flatten(start_dim=1))
        if self.lr_layer is not None:
            y_pred += self.lr_layer(X)
        if self.output_activation is not None:
            y_pred = self.output_activation(y_pred)
        return y_pred

# Cell
import torch
import torch.nn.functional as F

from .layers.common import FeaturesEmbedding, FeaturesLinear, MultiLayerPerceptron

# Cell
class AutoInt_v2(torch.nn.Module):
    """
    A pytorch implementation of AutoInt.
    Reference:
        W Song, et al. AutoInt: Automatic Feature Interaction Learning via Self-Attentive Neural Networks, 2018.
    """

    def __init__(self, field_dims, embed_dim, atten_embed_dim, num_heads, num_layers, mlp_dims, dropouts, has_residual=True):
        super().__init__()
        self.num_fields = len(field_dims)
        self.linear = FeaturesLinear(field_dims)
        self.embedding = FeaturesEmbedding(field_dims, embed_dim)
        self.atten_embedding = torch.nn.Linear(embed_dim, atten_embed_dim)
        self.embed_output_dim = len(field_dims) * embed_dim
        self.atten_output_dim = len(field_dims) * atten_embed_dim
        self.has_residual = has_residual
        self.mlp = MultiLayerPerceptron(self.embed_output_dim, mlp_dims, dropouts[1])
        self.self_attns = torch.nn.ModuleList([
            torch.nn.MultiheadAttention(atten_embed_dim, num_heads, dropout=dropouts[0]) for _ in range(num_layers)
        ])
        self.attn_fc = torch.nn.Linear(self.atten_output_dim, 1)
        if self.has_residual:
            self.V_res_embedding = torch.nn.Linear(embed_dim, atten_embed_dim)

    def forward(self, x):
        """
        :param x: Long tensor of size ``(batch_size, num_fields)``
        """
        embed_x = self.embedding(x)
        atten_x = self.atten_embedding(embed_x)
        cross_term = atten_x.transpose(0, 1)
        for self_attn in self.self_attns:
            cross_term, _ = self_attn(cross_term, cross_term, cross_term)
        cross_term = cross_term.transpose(0, 1)
        if self.has_residual:
            V_res = self.V_res_embedding(embed_x)
            cross_term += V_res
        cross_term = F.relu(cross_term).contiguous().view(-1, self.atten_output_dim)
        x = self.linear(x) + self.attn_fc(cross_term) + self.mlp(embed_x.view(-1, self.embed_output_dim))
        return torch.sigmoid(x.squeeze(1))