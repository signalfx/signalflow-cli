#!/usr/bin/env python
# -*- coding: utf-8 -*-

# An interactive command-line prompt for running real-time streaming SignalFlow
# analytics.

from __future__ import print_function

import argparse
import atexit
from contextlib import closing
import datetime
import os
import pprint
import pytz
import readline
import signalfx
import tslib
import sys

_DATE_FORMAT = '%Y-%m-%d %H:%M:%S %Z%z'
_TICKS = [' ', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']


class SignalFlowCli(object):

    def __init__(self, sfx, tz=pytz.utc):
        self._sfx = sfx
        self._tz = tz

        self._flow = sfx.signalflow()
        self._sparks = {}

    def close(self):
        self._flow.close()

    def _date_from_utc_ts(self, ts):
        date = datetime.datetime.utcfromtimestamp(ts / 1000.0)
        return pytz.utc.localize(date)

    def _add_to_spark(self, tsid, value):
        if tsid not in self._sparks:
            self._sparks[tsid] = [None] * 10
        self._sparks[tsid][-1] = value

    def _tick_sparks(self):
        for tsid in self._sparks.keys():
            self._sparks[tsid] = self._sparks[tsid][1:] + [None]

    def _render_spark_line(self, spark):
        values = filter(None, spark)
        maximum = max(values) if values else None
        minimum = min(values) if values else None

        def to_tick_index(v):
            if v and minimum != maximum:
                return 1 + int((len(_TICKS) - 2) * (v - minimum) /
                               (maximum - minimum))
            return 0

        return ''.join(map(lambda v: _TICKS[to_tick_index(v)], spark))

    def live_stream(self, program, **params):
        print('Requesting computation...', end=' ')
        sys.stdout.flush()

        try:
            c = self._flow.execute(program, **params)
        except signalfx.signalflow.ComputationExecutionError as e:
            if not e.message:
                print('failed ({0})!'.format(e.code))
            else:
                print('failed!')
                print('\033[31;1m{0}\033[;0m'.format(e.message))
            return

        print('waiting for data...', end=' ')
        sys.stdout.flush()

        try:
            for message in c.stream():
                if isinstance(message, signalfx.signalflow.EventMessage):
                    # skip those for now
                    continue

                ts = message.logical_timestamp_ms
                date = self._date_from_utc_ts(ts)
                print('\033[K\rAt \033[;1m{0}\033[;0m (Δ: {1}):'
                      .format(
                          date.astimezone(self._tz).strftime(_DATE_FORMAT),
                          tslib.render_delta(date)))

                self._tick_sparks()

                for tsid, value in message.data.items():
                    self._add_to_spark(tsid, value)

                for tsid, spark in self._sparks.items():
                    print('\033[K\r{repr:<60}: [{spark:10s}] '
                          .format(repr=c.get_timeseries_repr(tsid),
                                  spark=self._render_spark_line(spark)),
                          end='')
                    if spark[-1]:
                        print('\033[;1m{0:>10.2f}\033[;0m'.format(spark[-1]))
                    else:
                        print('{:>10s}'.format('-'))

                print('\r\033[{0}A'.format(len(self._sparks)+1), end='')
        except KeyboardInterrupt:
            pass
        finally:
            print('\033[{0}B'.format(len(self._sparks)+1))
            self._sparks.clear()
            c.close()


def main():
    parser = argparse.ArgumentParser(
        description='SignalFlow analytics interactive command-line client')
    parser.add_argument('-t', '--token', metavar='TOKEN',
                        help='Your session token')
    parser.add_argument('--api-endpoint', metavar='URL',
                        default='https://api.signalfx.com',
                        help='Override the base API endpoint URL')
    parser.add_argument('--timezone', metavar='TZ',
                        default='US/Pacific',
                        help='Override display timezone')
    options = parser.parse_args()

    # Setup the readline prompt.
    try:
        histfile = os.path.join(os.path.dirname(__file__),
                                '..', '.signalflow.history')
        atexit.register(readline.write_history_file, histfile)
        readline.parse_and_bind('tab: complete')
        readline.read_history_file(histfile)
    except IOError:
        pass

    params = {
        'start': '-15s',
        'stop': None,
        'resolution': '1s',
        'max_delay': None
    }

    def set_param(param, value=None):
        if param not in params:
            print('Unknown parameter {0} !'.format(param))
            return
        params[param] = value

    def get_params():
        r = {}
        for p in ['start', 'stop']:
            if params[p]:
                r[p] = tslib.parse_to_timestamp(params[p])
        for p in ['resolution', 'max_delay']:
            if params[p]:
                v = '={0}'.format(params[p])
                r[p] = tslib.parse_to_timestamp(v)
        return r

    with closing(SignalFlowCli(
            signalfx.SignalFx(options.token,
                              api_endpoint=options.api_endpoint),
            tz=pytz.timezone(options.timezone))) as cli:
        print('\033[31;1m-*-\033[;0m '
              '\033[;1mSignalFx SignalFlow™ Analytics Console\033[;0m '
              '\033[31;1m-*-\033[;0m')
        print()
        print('Set parameters with ".<param> <value>"; '
              'see current settings with "."')
        print('Enter your program and press ^D to execute. '
              'To exit, just press ^D.')
        print()

        while True:
            program = []
            while True:
                try:
                    command = raw_input('> ').strip()
                except (KeyboardInterrupt, EOFError):
                    print()
                    break

                if not command:
                    continue

                if command.startswith('.'):
                    if len(command) > 1:
                        set_param(*command[1:].split(' ', 1))
                    pprint.pprint(params)
                    continue

                program.append(command)

            if not program:
                break

            try:
                cli.live_stream('\n'.join(program), **get_params())
            except Exception as e:
                print(e)

    return 0


if __name__ == '__main__':
    sys.exit(main())
