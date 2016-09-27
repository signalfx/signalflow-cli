#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016 SignalFx, Inc. All Rights Reserved.

from __future__ import print_function

import csv
from signalfx import signalflow
import six
import sys

from . import utils


def stream(flow, program, start, stop, resolution, max_delay):
    """Execute a SignalFlow computation and output the results as CSV.

    :param flow: An open SignalFlow client connection.
    :param program: The program to execute.
    :param start: The absolute start timestamp, in milliseconds since Epoch.
    :param stop: An optional stop timestamp, in milliseconds since Epoch, or
        None for infinite streaming.
    :param resolution: The desired compute resolution, in milliseconds.
    :param max_delay: The desired maximum data wait, in milliseconds, or None
        for automatic.
    """

    buf = six.stringio.StringIO()
    writer = csv.writer(buf, dialect=csv.excel, quoting=csv.QUOTE_NONNUMERIC)

    def _message(msg):
        utils.message(msg, out=sys.stderr)

    def _emit(row):
        writer.writerow(row)
        line = buf.getvalue().strip()
        buf.truncate(0)
        buf.seek(0)
        return line

    try:
        _message('Requesting computation...')
        c = flow.execute(program, start=start, stop=stop,
                         resolution=resolution, max_delay=max_delay,
                         persistent=False)
    except Exception as e:
        _message('\r\033[K')
        _message(e)
        return

    header = None
    try:
        for message in c.stream():
            if isinstance(message, signalflow.messages.JobStartMessage):
                _message(' started; waiting for data...')
                continue

            if isinstance(message, signalflow.messages.JobProgressMessage):
                _message(' {0}%'.format(message.progress))
                continue

            if not isinstance(message, signalflow.messages.DataMessage):
                continue

            # At this point, metadata will be available
            if not header:
                header = ['timestamp']
                header.extend([utils.timeseries_repr(c.get_metadata(tsid))
                               for tsid in c.get_known_tsids()])
                _message('\n')
                yield _emit(header)

            # Note: this assumes that membership of the job doesn't
            # change during the stream.
            row = [message.logical_timestamp_ms]
            for tsid in c.get_known_tsids():
                row.append(message.data.get(tsid, ''))
            yield _emit(row)
    except KeyboardInterrupt:
        pass
    finally:
        c.close()
