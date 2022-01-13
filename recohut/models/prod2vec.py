# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/models/models.prod2vec.ipynb (unless otherwise specified).

__all__ = ['Prod2Vec', 'Prod2Vec_v2']

# Cell
from typing import List

import logging
import gensim
import numpy as np

# Cell
class Prod2Vec(object):
    """
    Implementation of the Prod2Vec skipgram model from
    Grbovic Mihajlo, Vladan Radosavljevic, Nemanja Djuric, Narayan Bhamidipati, Jaikit Savla, Varun Bhagwan, and Doug Sharp.
    "E-commerce in your inbox: Product recommendations at scale."
    In Proceedings of the 21th ACM SIGKDD International Conference on Knowledge Discovery and Data Mining,
    pp. 1809-1818. ACM, 2015.
    """

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger()

    def __init__(self, min_count=2, negative=5, size=100, window=5, decay_alpha=0.9):
        """
        :param min_count: (optional) the minimum item frequency. Items less frequent that min_count will be pruned
        :param negative: (optional) the minimum negative samples
        :param size: (optional) the size of the embeddings
        :param window: (optional) the size of the context window
        :param decay_alpha: (optional) the exponential decay factor used to discount the similarity scores for items
                back in the user profile. Lower values mean higher discounting of past user interactions. Allows values in [0-1].
        """
        super(Prod2Vec, self).__init__()
        self.min_count = min_count
        self.negative = negative
        self.size = size
        self.window = window
        self.decay_alpha = decay_alpha

    def __str__(self):
        return 'Prod2Vec(min_count={min_count}, ' \
               'size={size}, ' \
               'window={window}, ' \
               'decay_alpha={decay_alpha})'.format(**self.__dict__)

    def fit(self, train_data):
        self.model = gensim.models.Word2Vec(train_data,
                                            min_count=self.min_count,
                                            negative=self.negative,
                                            window=self.window,
                                            hs=1,
                                            size=self.size,
                                            sg=1,
                                            workers=-1)
        self.model.train(train_data, total_examples = self.model.corpus_count,
                         epochs=10, report_delay=1)
        # As we do not plan to train the model any further, we are calling
        # init_sims(), which will make the model much more memory-efficient
        self.model.init_sims(replace=True)

    def aggregate_vectors(self, products):
        product_vec = []
        for i in products:
            try:
                product_vec.append(self.model[i])
            except KeyError:
                continue

        return np.mean(product_vec, axis=0)

    def recommend(self, user_profile, topk=5):
        """
        Given the user profile return a list of recommendation

        Args:
            user_profile: list of item ids visited/interacted by the user
            topk: (optional) top-k recommendations
        """
        rec = []
        try:
            vec = self.aggregate_vectors(user_profile)
            # extract most similar products for the input vector
            rec = self.model.wv.similar_by_vector(vec, topn= topk+1)[1:]
        except KeyError:
            rec = []

        return rec

# Cell
import gensim
import numpy as np
import os
from abc import ABC
import ast

# Cell
class Prod2Vec_v2(ABC):
    def __init__(self):
        pass

    def train(self, items, iterations=15):
        # Get the item ID and rating for each item for each unique user
        x_train = [[str((x["sid"], x["rating"])) for x in y] for y in items]
        self._model = self.train_embeddings(x_train, iterations=iterations)

    def train_embeddings(
        self,
        sessions: list,
        min_c: int = 3,
        size: int = 48,
        window: int = 5,
        iterations: int = 15,
        ns_exponent: float = 0.75,
        is_debug: bool = True):
        """
        Train CBOW to get product embeddings with sensible defaults
        (https://arxiv.org/abs/2007.14906).
        """
        model = gensim.models.Word2Vec(min_count=min_c,
                                    size=size,
                                    window=window,
                                    iter=iterations,
                                    ns_exponent=ns_exponent)

        model.build_vocab(sessions)
        model.init_sims(replace=True)

        return model.wv

    def predict(self, prediction_input, *args, **kwargs):
        """
        Predicts the top 10 similar items recommended for each user according
        to the items that they've interacted and the ratings that they've given
        :param prediction_input: a list of lists containing a dictionary for
                                 each item interacted by that user
        :return:
        """
        all_predictions = []
        for items in prediction_input:
            predictions = []
            emb_vecs = []
            for item in items:
                emb_vec = self.get_vector(item)
                if emb_vec:
                    emb_vecs.append(emb_vec)
            if emb_vecs:
                # Calculate the average of all the latent vectors representing
                # the items interacted by the user as is done in https://arxiv.org/abs/2007.14906
                avg_emb_vec = np.mean(emb_vecs, axis=0)
                nn_products = self.model.similar_by_vector(avg_emb_vec, topn=10)
                for elem in nn_products:
                    elem = ast.literal_eval(elem[0])
                    predictions.append({"sid": elem[0], "rating": elem[1]})
            all_predictions.append(predictions)
        return all_predictions

    def get_vector(self, x):
        """
        Returns the latent vector that corresponds to the item ID and the rating
        :param x:
        :return:
        """
        item = str((x["sid"], x["rating"]))
        try:
            return list(self.model.get_vector(item))
        except Exception as e:
            return []

    @property
    def model(self):
        return self._model