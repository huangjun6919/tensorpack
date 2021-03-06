# -*- coding: UTF-8 -*-
# File: regularize.py
# Author: Yuxin Wu <ppwwyyxx@gmail.com>

import tensorflow as tf
import re

from ..utils import logger
from ..utils.argtools import graph_memoized
from ..tfutils.tower import get_current_tower_context
from .common import layer_register

__all__ = ['regularize_cost', 'l2_regularizer', 'l1_regularizer', 'Dropout']


@graph_memoized
def _log_regularizer(name):
    logger.info("Apply regularizer for {}".format(name))


l2_regularizer = tf.contrib.layers.l2_regularizer
l1_regularizer = tf.contrib.layers.l1_regularizer


def regularize_cost(regex, func, name='regularize_cost'):
    """
    Apply a regularizer on trainable variables matching the regex.
    In replicated mode, will only regularize variables within the current tower.

    Args:
        regex (str): a regex to match variable names, e.g. "conv.*/W"
        func: the regularization function, which takes a tensor and returns a scalar tensor.

    Returns:
        tf.Tensor: the total regularization cost.

    Example:
        .. code-block:: python

            cost = cost + regularize_cost("fc.*/W", l2_regularizer(1e-5))
    """
    ctx = get_current_tower_context()
    params = tf.trainable_variables()

    # If vars are shared, use all of them
    # If vars are replicated, only regularize those in the current tower
    params = ctx.filter_vars_by_vs_name(params)

    with tf.name_scope('regularize_cost'):
        costs = []
        for p in params:
            para_name = p.name
            if re.search(regex, para_name):
                costs.append(func(p))
                _log_regularizer(para_name)
        if not costs:
            return tf.constant(0, dtype=tf.float32, name='empty_' + name)
    return tf.add_n(costs, name=name)


def regularize_cost_from_collection(name='regularize_cost'):
    """
    Get the cost from the regularizers in ``tf.GraphKeys.REGULARIZATION_LOSSES``.
    In replicated mode, will only regularize variables within the current tower.

    Returns:
        a scalar tensor, the regularization loss.
    """
    regularization_losses = set(tf.get_collection(tf.GraphKeys.REGULARIZATION_LOSSES))
    ctx = get_current_tower_context()
    if len(regularization_losses) > 0:
        # NOTE: this collection doesn't grow with towers.
        # It is only added with variables that are newly created.
        if ctx.has_own_variables:   # be careful of the first tower (name='')
            regularization_losses = ctx.filter_vars_by_vs_name(regularization_losses)
        print([k.name for k in regularization_losses])
        logger.info("Add REGULARIZATION_LOSSES of {} tensors on the total cost.".format(len(regularization_losses)))
        reg_loss = tf.add_n(list(regularization_losses), name=name)
        return reg_loss
    else:
        return tf.constant(0, dtype=tf.float32, name='empty_' + name)


@layer_register(log_shape=False, use_scope=False)
def Dropout(x, keep_prob=0.5, is_training=None, noise_shape=None):
    """
    Dropout layer as in the paper `Dropout: a Simple Way to Prevent
    Neural Networks from Overfitting <http://dl.acm.org/citation.cfm?id=2670313>`_.

    Args:
        keep_prob (float): the probability that each element is kept. It is only used
            when is_training=True.
        is_training (bool): If None, will use the current :class:`tensorpack.tfutils.TowerContext`
            to figure out.
        noise_shape: same as `tf.nn.dropout`.
    """
    if is_training is None:
        is_training = get_current_tower_context().is_training
    keep_prob = tf.constant(keep_prob if is_training else 1.0)
    return tf.nn.dropout(x, keep_prob, noise_shape=noise_shape)
