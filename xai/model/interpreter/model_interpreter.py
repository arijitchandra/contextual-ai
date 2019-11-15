#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2019 SAP SE or an SAP affiliate company. All rights reserved
# ============================================================================


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import operator
import warnings

import numpy
from typing import List, Union, Dict, Tuple

from xai.explainer.explainer_factory import ExplainerFactory
from xai.model.interpreter.exceptions import InterpreterUninitializedError
from xai.model.interpreter.explanation_aggregator import ExplanationAggregator


################################################################################
### Model Interpreter
################################################################################
class ModelInterpreter:
    """
    Class for model interpreter

    This class is to help to interpret the model with a model-agnostic explainer.

    """
    def __init__(self, domain: str, algorithm: str = None):
        """
        Define the domain and algorithm for interpreter

        Args:
            domain (str): User-provided domain
            algorithm (str): User-provided unique identifier of the algorithm
        """
        self.domain = domain
        self.algorithm = algorithm
        self._explainer = None

    def build_interpreter(self, **kwargs):
        """
        Build and initialize model interpreter

        Args:
            **kwargs: build interpreter based on the domain and algorithm
        """
        self._explainer = ExplainerFactory.get_explainer(domain=self.domain, algorithm=self.algorithm)
        self._explainer.build_explainer(**kwargs)

    def interpret_model(self, samples: List[numpy.ndarray], stats_type: str = 'top_k', k: int = 5):
        """
        Get statistics of explanations generated by the pre-defined explainer from given samples

        Args:
            class_num: int, number of classes
            samples: list[numpy.ndarray], not None. A list of 1D numpy array corresponding to row/single examples
            stats_type: str, not None. The pre-defined stats_type for statistical analysis.
                        For details see `xai.model_interpreter.explanation_aggregator.get_statistics()`
            k:  int, not None. the k value for `top_k` method and `average_ranking`.
                It will be ignored if the stats type are not `top_k` or `average_ranking`.
                Default value of k is 5.

        Returns:
            A dictionary maps class label to the aggregated feature importance score.

        """
        if self._explainer:
            _explainer_aggregator = ExplanationAggregator(confidence_threshold=0.8)

            for idx, sample in enumerate(samples):
                exp = self._explainer.explain_instance(instance=sample, top_labels=1,
                                                       num_samples=max(len(samples) // 10, 100),
                                                       num_features=k)
                _explainer_aggregator.feed(explanation=exp)
                if (idx + 1) % 100 == 0:
                    warnings.warn(message='Interpret %s/%s samples' % (
                        idx + 1, len(samples)))
            return _explainer_aggregator.get_statistics(stats_type=stats_type, k=k)
        else:
            raise InterpreterUninitializedError('This interpreter is not yet instantiated! '
                                                'Please call build_interpreter()'
                                                'first before interpreting models.')

    def error_analysis(self, class_num: int, valid_x: List[numpy.ndarray], valid_y: Union[List[int], List[str]],
                       stats_type: str = 'top_k', k: int = 5) -> Dict[Union[Tuple[int, int], Tuple[str, str]], Dict]:
        """
        Aggregated the explaination based on confusion matrix cell, i.e. aggregated explanations for samples from
        class X and be predicted as class Y

        Args:
            class_num: int, number of classes
            valid_x: A list of 1D ndarray. Validation data.
            valid_y: A list of int or a list of str. Validation ground truth class label (str) or (index).
                     The type should be consistent to the classes label passed in when building the model interpreter.
            stats_type: str, pre-defined types. For now, it supports 3 types:
                            - top_k: how often a feature appears in the top K features in the explanation
                            - average_score: average score for each feature in the explanation
                            - average_ranking: average ranking for each feature in the explanation
                        Default type is `top_k`.
            k:  int, not None. the k value for `top_k` method and `average_ranking`.
                It will be ignored if the stats type are not `top_k` or `average_ranking`.
                Default value of k is 5.

        Returns:
            A dictionary maps a tuple (ground_truth_label, predicted_label) to a dict of important features
            for each class

        """
        error_analysis_dict = dict()
        for idx, (sample, gt_label) in enumerate(zip(valid_x, valid_y)):
            exp = self._explainer.explain_instance(instance=sample, top_labels=class_num,
                                                   num_samples=100,
                                                   num_features=k)
            prob = {_class: _class_exp['confidence'] for _class, _class_exp in exp.items()}
            predict_label = sorted(prob.items(), key=operator.itemgetter(1), reverse=1)[0][0]
            if predict_label != gt_label:
                if (gt_label, predict_label) not in error_analysis_dict.keys():
                    error_analysis_dict[(gt_label, predict_label)] = ExplanationAggregator(confidence_threshold=0)
                error_analysis_dict[(gt_label, predict_label)].feed(explanation=exp)
            if (idx + 1) % 10 == 0:
                warnings.warn(message='Analyze %s/%s samples' % (
                    idx + 1, len(valid_x)))

        error_analysis_stats = dict()
        for cm_cell, aggregator in error_analysis_dict.items():
            error_analysis_stats[cm_cell] = aggregator.get_statistics(stats_type=stats_type, k=k)

        return error_analysis_stats
