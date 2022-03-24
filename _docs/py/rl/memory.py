# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/rl/rl.memory.ipynb (unless otherwise specified).

__all__ = ['ReplayMemory']

# Cell
import random
from collections import deque

# Cell
class ReplayMemory(object):
    """
    Replay Memory
    """

    def __init__(self, buffer_size: int):
        """
        Initialize ReplayMemory
        :param buffer_size: size of the buffer
        """
        self.buffer_size = buffer_size
        self.buffer = deque(maxlen=buffer_size)

    def __len__(self):
        return len(self.buffer)

    def push(self, experience: tuple):
        """
        Push one experience into the buffer
        :param experience: (state, action, reward, new_state)
        """
        self.buffer.append(experience)

    def sample(self, batch_size: int):
        """
        Sample one batch from the buffer
        :param batch_size: number of experiences in the batch
        :return: batch
        """
        batch = random.sample(self.buffer, batch_size)
        return batch