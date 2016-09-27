#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016 SignalFx, Inc. All Rights Reserved.

from __future__ import print_function
import sys


_REPR_IGNORED_DIMENSIONS = set(['sf_metric',
                                'sf_originatingMetric',
                                'sf_eventType',
                                'sf_originatingEventType',
                                'jobId',
                                'programId'])


def message(s, out=sys.stdout):
    """Display the given message string with no new line and flush
    immediately."""
    out.write(s)
    out.flush()


def timeseries_repr(obj):
    """Return a representation of a timeseries' identity usable for
    display.

    The representation is split into three parts: the stream label, the
    fixed dimension (metric or eventType), and the variable dimensions. The
    label is only shown if present. The fixed dimension is either the
    primary fixed dimension (sf_metric or sf_eventType), unless it's a
    generated name, in which case we fallback to the sf_originating*
    version. Finally, all available variable dimensions are appended,
    dot-separated."""
    if not obj:
        return None

    result = []

    obj_type = obj.get('sf_type')
    if obj_type == 'MetricTimeSeries':
        candidates = ['sf_metric', 'sf_originatingMetric']
    elif obj_type == 'EventTimeSeries':
        candidates = ['sf_eventType', 'sf_originatingEventType']
    else:
        # We should not be seeing any other metadata object types.
        raise ValueError('Unknown metadata object of type {}'.format(obj_type))

    for c in candidates:
        if c in obj and not obj[c].lower().startswith('_sf_'):
            result.append(obj[c])
            break

    key = filter(lambda k: k not in _REPR_IGNORED_DIMENSIONS,
                 obj['sf_key'])
    name = '.'.join(map(lambda k: obj[k], sorted(key)))
    result.append(name)

    s = '/'.join(filter(None, result))

    # Prepend with label if present.
    label = obj.get('sf_streamLabel')
    if label:
        s = '{0}: {1}'.format(label, s)

    return s
