#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016 SignalFx, Inc. All Rights Reserved.

from __future__ import print_function
from ansicolor import green, red, white
import tslib
from signalfx import signalflow

from . import utils


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
    events = []

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
                return 3
            if not v:
                return 0
            return 1 + int((len(_TICKS) - 2) * (v - minimum) /
                           (maximum - minimum))

        return ''.join(map(lambda v: _TICKS[to_tick_index(v)], spark))

    def _render(c):
        """Render the data display. Starts by displaying the received data,
        followed by the events."""
        lines = 0

        if c.last_logical_ts:
            date = tslib.date_from_utc_ts(c.last_logical_ts)
            print('\033[K\rAt {date} (@{resolution}, Δ: {lag}):'.format(
                date=white(date.astimezone(tz).strftime(_DATE_FORMAT),
                           bold=True),
                resolution=tslib.render_delta(c.resolution)
                if c.resolution else '-',
                lag=tslib.render_delta_from_now(date)))

            for tsid, spark in sparks.items():
                print('\033[K\r{repr:<60}: [{spark:10s}] '
                      .format(repr=utils.timeseries_repr(c.get_metadata(tsid)),
                              spark=_render_spark_line(spark)),
                      end='')
                value = spark[-1]
                if type(value) == int:
                    print('\033[;1m{0:>10d}\033[;0m'.format(value))
                elif type(value) == float:
                    print('\033[;1m{0:>10.2f}\033[;0m'.format(value))
                else:
                    print('{:>10s}'.format('-'))

            lines += 1 + len(sparks)

        if events:
            print('\nEvents:')
            for event in events:
                date = tslib.date_from_utc_ts(event.timestamp_ms)
                is_now = event.properties['is']
                print(' {mark} {date} [{incident}]: {sources}'.format(
                    mark=green('✓') if is_now == 'ok' else red('✗'),
                    date=white(date.astimezone(tz).strftime(_DATE_FORMAT),
                               bold=True),
                    incident=event.properties['incidentId'],
                    sources=event.properties['sources']))

            lines += 2 + len(events)

        utils.message('\r\033[{0}A'.format(lines))

    utils.message('Requesting computation... ')
    try:
        c = flow.execute(program, start=start, stop=stop,
                         resolution=resolution, max_delay=max_delay,
                         persistent=False)
    except signalflow.errors.SignalFlowException as e:
        if not e.message:
            print('failed ({0})!'.format(e.code))
        else:
            print('failed!')
            print('\033[31;1m{0}\033[;0m'.format(e.message))
        return

    try:
        try:
            for message in c.stream():
                if isinstance(message, signalflow.messages.JobStartMessage):
                    utils.message(' started; waiting for data...')
                    continue

                if isinstance(message, signalflow.messages.JobProgressMessage):
                    utils.message(' {0}%'.format(message.progress))
                    continue

                # Messages types below all trigger a re-render.
                if isinstance(message, signalflow.messages.DataMessage):
                    _tick_sparks()
                    for tsid, value in message.data.items():
                        _add_to_spark(tsid, value)
                elif isinstance(message, signalflow.messages.EventMessage):
                    if len(events) == 5:
                        events.pop()
                    events.insert(0, message)

                _render(c)
        except KeyboardInterrupt:
            pass
        finally:
            print('\033[{0}B'.format(len(sparks) + len(events) + 2))
            c.close()
    except Exception as e:
        print('Oops ;-( {}'.format(e))
