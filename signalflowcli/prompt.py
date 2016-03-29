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
import sys
import tslib

from . import csvflow, graph, live
from .tzaction import TimezoneAction


def process_params(**kwargs):
    """Process the given parameters to expand relative, human-readable time
    offsets into their absolute millisecond value or absolute millisecond
    timestamp counterparts."""
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


def prompt(flow, tz, params):
    print('\033[31;1m-*-\033[;0m '
          '\033[;1mSignalFx SignalFlow™ Analytics Console\033[;0m '
          '\033[31;1m-*-\033[;0m')
    print()
    print('Set parameters with ".<param> <value>"; '
          'see current settings with "."')
    print('Enter your program and press ^D to execute. '
          'To stop streaming, or to exit, just press ^C.')
    print()

    def set_param(param, value=None):
        if param not in params:
            print('Unknown parameter {0} !'.format(param))
            return
        params[param] = value

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
                    set_param(*command[1:].split(' ', 1))
                pprint.pprint(params)
                continue

            program.append(command)

        if not program:
            break

        try:
            live.stream(flow, tz, '\n'.join(program),
                        **process_params(**params))
        except Exception as e:
            print('Oops ;-( {}'.format(e))

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
                        default=None,
                        help='compute resolution (default: auto)')
    parser.add_argument('-d', '--max-delay', metavar='MAX-DELAY',
                        default=None,
                        help='maximum data wait (default: auto)')
    parser.add_argument('--output', choices=['live', 'csv', 'graph'],
                        default='csv',
                        help='output format for non-interactive mode')
    parser.add_argument('program', nargs='?', type=file,
                        default=sys.stdin,
                        help='file to read program from (default: stdin)')
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
            prompt(flow, options.timezone, params)
        else:
            program = options.program.read()
            params = process_params(**params)
            if options.output == 'live':
                live.stream(flow, options.timezone, program, **params)
            else:
                data = csvflow.stream(flow, program, **params)
                if options.output == 'csv':
                    map(print, data)
                elif options.output == 'graph':
                    graph.render(data, options.timezone)
    finally:
        flow.close()
        sfx.stop()

    return 0

if __name__ == '__main__':
    sys.exit(main())
