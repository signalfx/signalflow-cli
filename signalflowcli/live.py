#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016 SignalFx, Inc. All Rights Reserved.

from __future__ import print_function
import tslib
import signalfx
import sys

_DATE_FORMAT = '%Y-%m-%d %H:%M:%S %Z%z'
_TICKS = [' ', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']


def stream(flow, tz, program, start, stop, resolution, max_delay):
    """Execute a streaming SignalFlow computation and display the results in
    the terminal with live sparklines.

    :param flow: An open SignalFlow client connection.
    :param tz: A pytz timezone for date and time representations.
    :param program: The program to execute.
    :param start: The absolute start timestamp, in milliseconds since Epoch.
    :param stop: An optional stop timestamp, in milliseconds since Epoch, or
        None for infinite streaming.
    :param resolution: The desired compute resolution, in milliseconds.
    :param max_delay: The desired maximum data wait, in milliseconds, or None
        for automatic.
    """

    sparks = {}

    def _add_to_spark(tsid, value):
        """Add the given value to a time series' sparkline."""
        if tsid not in sparks:
            sparks[tsid] = [None] * 10
        sparks[tsid][-1] = value

    def _tick_sparks():
        """Tick (advance) all sparklines."""
        for tsid in sparks.keys():
            sparks[tsid] = sparks[tsid][1:] + [None]

    def _render_spark_line(spark):
        """Return a visual representation of a time series' sparkline."""
        values = filter(None, spark)
        maximum = max(values) if values else None
        minimum = min(values) if values else None

        def to_tick_index(v):
            if minimum == maximum:
                return 5
            if not v:
                return 0
            return 1 + int((len(_TICKS) - 2) * (v - minimum) /
                           (maximum - minimum))

        return ''.join(map(lambda v: _TICKS[to_tick_index(v)], spark))

    def _output(message):
        print(message, end='')
        sys.stdout.flush()

    _output('Requesting computation...')
    try:
        c = flow.execute(program, start=start, stop=stop,
                         resolution=resolution, max_delay=max_delay,
                         persistent=False)
    except signalfx.signalflow.ComputationExecutionError as e:
        if not e.message:
            print('failed ({0})!'.format(e.code))
        else:
            print('failed!')
            print('\033[31;1m{0}\033[;0m'.format(e.message))
        return

    _output(' waiting for data...')
    try:
        for message in c.stream():
            if not isinstance(message, signalfx.signalflow.DataMessage):
                continue

            ts = message.logical_timestamp_ms
            date = tslib.date_from_utc_ts(ts)
            print('\033[K\rAt \033[;1m{0}\033[;0m (@{1}, Δ: {2}):'
                  .format(date.astimezone(tz).strftime(_DATE_FORMAT),
                          tslib.render_delta(c.resolution)
                          if c.resolution else '-',
                          tslib.render_delta_from_now(date)))

            _tick_sparks()

            for tsid, value in message.data.items():
                _add_to_spark(tsid, value)

            for tsid, spark in sparks.items():
                print('\033[K\r{repr:<60}: [{spark:10s}] '
                      .format(repr=c.get_timeseries_repr(tsid),
                              spark=_render_spark_line(spark)),
                      end='')
                if spark[-1]:
                    print('\033[;1m{0:>10.2f}\033[;0m'.format(spark[-1]))
                else:
                    print('{:>10s}'.format('-'))

            _output('\r\033[{0}A'.format(len(sparks)+1))
    except KeyboardInterrupt:
        pass
    finally:
        print('\033[{0}B'.format(len(sparks)+1))
        c.close()
