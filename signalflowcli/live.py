#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016 SignalFx, Inc. All Rights Reserved.

from __future__ import print_function
from ansicolor import green, red, white
import json
import tslib
from signalfx import signalflow
import six

from . import utils


class LiveOutputDisplay(object):

    _DATE_FORMAT = '%Y-%m-%d %H:%M:%S %Z%z'
    _TICKS = [' ', '▁', '▂', '▃', '▅', '▆', '▇']
    _LATEST_EVENTS_COUNT = 5

    def __init__(self, computation, tz):
        self._computation = computation
        self._tz = tz

        # Sparkline data
        self._sparks = {}

        # Latest events (up to _LATEST_EVENTS_COUNT)
        self._events = []

    def _add_to_spark(self, tsid, value):
        """Add the given value to a time series' sparkline."""
        if tsid not in self._sparks:
            self._sparks[tsid] = [None] * 10
        self._sparks[tsid][-1] = value

    def _tick_sparks(self):
        """Tick (advance) all sparklines."""
        for tsid in self._sparks.keys():
            self._sparks[tsid] = self._sparks[tsid][1:] + [None]

    def _render_date(self, date):
        return (date.astimezone(self._tz)
                .strftime(LiveOutputDisplay._DATE_FORMAT))

    def _render_spark_line(self, spark):
        """Return a visual representation of a time series' sparkline."""
        values = list(filter(None, spark))
        maximum = max(values) if values else None
        minimum = min(values) if values else None

        def to_tick_index(v):
            if minimum == maximum:
                return 3
            if not v:
                return 0
            return 1 + int((len(LiveOutputDisplay._TICKS) - 2) *
                           (v - minimum) / (maximum - minimum))

        return ''.join(map(
            lambda v: LiveOutputDisplay._TICKS[to_tick_index(v)],
            spark))

    def _render_latest_data(self):
        """Render the latest data with sparkline for each timeseries."""
        date = tslib.date_from_utc_ts(self._computation.last_logical_ts)
        print('\033[K\rAt {date} (@{resolution}, Δ: {lag}):'.format(
            date=white(self._render_date(date), bold=True),
            resolution=tslib.render_delta(self._computation.resolution)
            if self._computation.resolution else '-',
            lag=tslib.render_delta_from_now(date)))

        for tsid, spark in self._sparks.items():
            metadata = self._computation.get_metadata(tsid)
            print('\033[K\r{repr:<60}: [{spark:10s}] '
                  .format(repr=utils.timeseries_repr(metadata) or '',
                          spark=self._render_spark_line(spark)),
                  end='')
            value = spark[-1]
            if type(value) == int:
                print('\033[;1m{0:>10d}\033[;0m'.format(value))
            elif type(value) == float:
                print('\033[;1m{0:>10.2f}\033[;0m'.format(value))
            else:
                print('{:>10s}'.format('-'))

        return len(self._sparks) + 1

    def _render_latest_events(self):
        """Render the latest events emitted by the computation.

        TODO(mpetazzoni): render custom events/alert events differently and
        support alert event schema v3.
        """
        print('\nEvents:')

        def maybe_json(v):
            if isinstance(v, six.string_types):
                return json.loads(v)
            return v

        for event in self._events:
            ets = self._computation.get_metadata(event.tsid)
            contexts = json.loads(ets.get('sf_detectInputContexts', '{}'))

            sources = maybe_json(event.properties.get('inputSources', '{}'))
            sources = ', '.join([
                '{0}: {1}'.format(white(contexts[k].get('identifier', k)), v)
                for k, v in sources.items()])

            values = maybe_json(event.properties.get('inputValues', '{}'))
            values = ', '.join([
                '{0}={1}'.format(contexts[k].get('identifier', k), v)
                for k, v in values.items()])

            date = tslib.date_from_utc_ts(event.timestamp_ms)
            is_now = event.properties['is']

            print(' {mark} {date} [{incident}]: {sources} | {values}'
                  .format(mark=green('✓') if is_now == 'ok' else red('✗'),
                          date=white(self._render_date(date), bold=True),
                          incident=event.properties['incidentId'],
                          sources=sources,
                          values=values))

        return 2 + len(self._events)

    def _render(self):
        """Render the data display. Starts by displaying the received data,
        followed by the events."""
        lines = 0
        if self._computation.last_logical_ts:
            lines += self._render_latest_data()
        if self._events:
            lines += self._render_latest_events()
        utils.message('\033[{0}A'.format(lines))

    def stream(self):
        try:
            for message in self._computation.stream():
                if isinstance(message, signalflow.messages.JobStartMessage):
                    utils.message(' started; waiting for data...')
                    continue

                if isinstance(message, signalflow.messages.JobProgressMessage):
                    utils.message(' {0}%'.format(message.progress))
                    continue

                # Messages types below all trigger a re-render.
                if isinstance(message, signalflow.messages.DataMessage):
                    self._tick_sparks()
                    for tsid, value in message.data.items():
                        self._add_to_spark(tsid, value)
                    self._render()
                elif isinstance(message, signalflow.messages.EventMessage):
                    if len(self._events) == \
                            LiveOutputDisplay._LATEST_EVENTS_COUNT:
                        self._events.pop()
                    self._events.insert(0, message)
                    self._render()
        except KeyboardInterrupt:
            pass
        finally:
            print('\033[{0}B'.format(len(self._sparks)+len(self._events)+2))
            self._computation.close()


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
        LiveOutputDisplay(c, tz).stream()
    except Exception as e:
        print('Oops ;-( {}'.format(e))
