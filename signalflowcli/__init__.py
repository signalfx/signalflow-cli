#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016 SignalFx, Inc. All Rights Reserved.

"""SignalFlow CLI.

An interactive command-line prompt for running real-time streaming SignalFx
SignalFlow Analytics.
"""

from __future__ import print_function

import argparse
import atexit
import os
import pprint
import readline
import signalfx
import tslib
import sys

from . import csvflow, live
from .tzaction import TimezoneAction


__author__ = 'SignalFx, Inc'
__email__ = 'info@signalfx.com'
__copyright__ = 'Copyright (C) 2016 SignalFx, Inc. All rights reserved.'


def _set_param(params, param, value=None):
    if param not in params:
        print('Unknown parameter {0} !'.format(param))
        return
    params[param] = value


def _process_params(**kwargs):
    r = dict(kwargs)
    for k, v in r.items():
        if not v:
            continue
        if k in ['start', 'stop']:
            r[k] = tslib.parse_to_timestamp(v)
        if k in ['resolution', 'max_delay']:
            v = '={0}'.format(v)
            r[k] = tslib.parse_to_timestamp(v)
    return r


def _prompt(flow, tz, params):
    print('\033[31;1m-*-\033[;0m '
          '\033[;1mSignalFx SignalFlow™ Analytics Console\033[;0m '
          '\033[31;1m-*-\033[;0m')
    print()
    print('Set parameters with ".<param> <value>"; '
          'see current settings with "."')
    print('Enter your program and press ^D to execute. '
          'To stop streaming, or to exit, just press ^C.')
    print()

    # Setup the readline prompt.
    try:
        histfile = os.path.join(os.path.dirname(__file__),
                                '..', '.signalflow.history')
        atexit.register(readline.write_history_file, histfile)
        readline.parse_and_bind('tab: complete')
        readline.read_history_file(histfile)
    except IOError:
        pass

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
                    _set_param(params, *command[1:].split(' ', 1))
                pprint.pprint(params)
                continue

            program.append(command)

        if not program:
            break

        try:
            live.stream(flow, tz, '\n'.join(program),
                        **_process_params(**params))
        except Exception as e:
            print(e)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='SignalFlow Analytics interactive command-line client')
    parser.add_argument('-t', '--token', metavar='TOKEN',
                        help='Your session token')
    parser.add_argument('--api-endpoint', metavar='URL',
                        default='https://api.signalfx.com',
                        help='Override the base API endpoint URL')
    parser.add_argument('-a', '--start', metavar='START',
                        default='-1m',
                        help='start timestamp or delta (default: -15m)')
    parser.add_argument('-o', '--stop', metavar='STOP',
                        default=None,
                        help='stop timestamp or delta (default: infinity)')
    parser.add_argument('-r', '--resolution', metavar='RESOLUTION',
                        default='1s',
                        help='compute resolution (default: 1s)')
    parser.add_argument('-d', '--max-delay', metavar='MAX-DELAY',
                        default=None,
                        help='maximum data wait (default: auto)')
    TimezoneAction.add_to_parser(parser)
    options = parser.parse_args()

    params = {
        'start': options.start,
        'stop': options.stop,
        'resolution': options.resolution,
        'max_delay': options.max_delay,
    }

    sfx = signalfx.SignalFx(options.token,
                            api_endpoint=options.api_endpoint)
    flow = sfx.signalflow()

    try:
        if sys.stdin.isatty():
            _prompt(flow, options.timezone, params)
        else:
            map(print, csvflow.stream(flow, sys.stdin.read(),
                                      **_process_params(**params)))
    finally:
        flow.close()
        sfx.stop()

    return 0

if __name__ == '__main__':
    sys.exit(main())
