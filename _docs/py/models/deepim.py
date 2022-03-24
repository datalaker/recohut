# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/models/models.deepim.ipynb (unless otherwise specified).

__all__ = ['DeepIM']

# Cell
import torch
from torch import nn

from .layers.embedding import EmbeddingLayer
from .layers.common import MLP_Layer
from .layers.interaction import InteractionMachine

from .bases.ctr import CTRModel

# Cell
class DeepIM(CTRModel):
    def __init__(self,
                 feature_map,
                 model_id="DeepIM",
                 task="binary_classification",
                 learning_rate=1e-3,
                 embedding_initializer="torch.nn.init.normal_(std=1e-4)",
                 embedding_dim=10,
                 im_order=2,
                 im_batch_norm=False,
                 hidden_units=[64, 64, 64],
                 hidden_activations="ReLU",
                 net_dropout=0,
                 batch_norm=False,
                 **kwargs):
        super(DeepIM, self).__init__(feature_map,
                                           model_id=model_id,
                                           **kwargs)
        self.embedding_layer = EmbeddingLayer(feature_map, embedding_dim)
        self.im_layer = InteractionMachine(embedding_dim, im_order, im_batch_norm)
        self.dnn = MLP_Layer(input_dim=embedding_dim * feature_map.num_fields,
                             output_dim=1,
                             hidden_units=hidden_units,
                             hidden_activations=hidden_activations,
                             output_activation=None,
                             dropout_rates=net_dropout,
                             batch_norm=batch_norm) \
                   if hidden_units is not None else None
        self.output_activation = self.get_final_activation(task)
        self.init_weights(embedding_initializer=embedding_initializer)

    def forward(self, inputs):
        feature_emb = self.embedding_layer(inputs)
        y_pred = self.im_layer(feature_emb)
        if self.dnn is not None:
            y_pred += self.dnn(feature_emb.flatten(start_dim=1))
        if self.output_activation is not None:
            y_pred = self.output_activation(y_pred)
        return y_pred