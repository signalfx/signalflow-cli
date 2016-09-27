#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016 SignalFx, Inc. All Rights Reserved.

"""SignalFlow CLI.

An interactive command-line prompt for running real-time streaming SignalFx
SignalFlow Analytics.
"""

from __future__ import print_function

from ansicolor import red, white
import argparse
import getpass
import os
import pprint
import prompt_toolkit
import prompt_toolkit.contrib.completers
import pygments
import pygments_signalflow
import requests
import signalfx
import sys
import tslib

from . import csvflow, graph, live, utils
from .tzaction import TimezoneAction

# Default search location for a SignalFx session token file.
# Used if no token was provided with the --token option.
_DEFAULT_TOKEN_FILE = '~/.sftoken'


class OptionCompleter(prompt_toolkit.completion.Completer):

    OPTS = ['start', 'stop', 'resolution', 'max_delay', 'output']

    def get_completions(self, document, complete_event):
        for opt in self.OPTS:
            if opt.startswith(document.text_before_cursor):
                yield prompt_toolkit.completion.Completion(
                        opt, start_position=-document.cursor_position)


class PromptCompleter(prompt_toolkit.completion.Completer):

    fs_completer = prompt_toolkit.contrib.completers.PathCompleter()
    opt_completer = OptionCompleter()

    def _offset(self, document, offset=1):
        return prompt_toolkit.document.Document(
                document.text[offset:], document.cursor_position - offset)

    def get_completions(self, document, complete_event):
        if document.text.startswith('!'):
            return self.fs_completer.get_completions(
                    self._offset(document), complete_event)
        elif document.text.startswith('.'):
            return self.opt_completer.get_completions(
                    self._offset(document), complete_event)
        return []


def prompt_for_token(api_endpoint):
    print('Please enter your credentials for {0}.'.format(api_endpoint))
    print('To avoid having to login manually, use the --token option.')
    print()
    email = raw_input('Email: ')
    password = getpass.getpass('Password: ')
    try:
        print()
        utils.message('Logging in as {0}... '.format(email))
        response = requests.post('{0}/v2/session'.format(api_endpoint),
                                 json={'email': email, 'password': password})
        response.raise_for_status()
        token = response.json()['accessToken']
        print('ok.')
        print()
        return token
    finally:
        del password


def find_session_token(options):
    # Obviously, if a token was provided, use it.
    if options.token:
        return options.token

    # Otherwise, try to load a token from _DEFAULT_TOKEN_FILE.
    try:
        with open(os.path.expanduser(_DEFAULT_TOKEN_FILE)) as f:
            return f.read().strip()
    except:
        pass

    # If we still don't have a token, we need to prompt the user, but only if
    # we have a tty.
    if not sys.stdin.isatty():
        sys.stderr.write('Authentication token must be specified with '
                         '--token for non-interactive mode!\n')
        return None

    try:
        return prompt_for_token(options.api_endpoint)
    except KeyboardInterrupt:
        return None
    except Exception as e:
        print('failed!')
        print(e)
        return None


def process_params(**kwargs):
    """Process the given parameters to expand relative, human-readable time
    offsets into their absolute millisecond value or absolute millisecond
    timestamp counterparts."""
    r = dict(kwargs)
    del r['output']
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
    print(red('-*-', bold=True) + ' ' +
          white('SignalFx SignalFlow™ Analytics Console', bold=True) + ' ' +
          red('-*-', bold=True))
    print()
    print(white('Enter your program and press <Esc><Enter> to execute.'))
    print('SignalFlow programs may span multiple lines.')
    print('Set parameters with ".<param> <value>"; '
          'see current settings with "."')
    print('To stop streaming, or to exit, just press ^C.')
    print()

    def set_param(param, value=None):
        if param not in params:
            print('Unknown parameter {0} !'.format(param))
            return
        params[param] = value

    history = prompt_toolkit.history.FileHistory(
            os.path.expanduser('~/.signalflow.history'))

    while True:
        program = []
        try:
            prompt_args = {
                'lexer': prompt_toolkit.layout.lexers.PygmentsLexer(
                    pygments_signalflow.SignalFlowLexer),
                'history': history,
                'auto_suggest':
                    prompt_toolkit.auto_suggest.AutoSuggestFromHistory(),
                'get_continuation_tokens':
                    lambda c, w: [(pygments.token.Token, '>>')],
                'completer': PromptCompleter(),
                'multiline': True,
            }
            program = prompt_toolkit.shortcuts.prompt(
                    u'-> ', **prompt_args).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not program:
            continue

        # Parameter access and changes
        if program.startswith('.'):
            if len(program) > 1:
                set_param(*program[1:].split(' ', 1))
            pprint.pprint(params)
            continue

        # Execute from file
        if program.startswith('!'):
            filename = program[1:].strip()
            try:
                with open(filename) as f:
                    program = f.read()
            except:
                print('Cannot read program from {0}!'.format(filename))
                continue
            print('Executing program from {0}:'.format(filename))
            print(program)
        exec_params = process_params(**params)
        output = params.get('output') or 'live'

        try:
            if output == 'live':
                live.stream(flow, tz, program, **exec_params)
            elif output in ['csv', 'graph']:
                data = csvflow.stream(flow, program, **exec_params)
                if output == 'csv':
                    map(print, data)
                elif output == 'graph':
                    graph.render(data, tz)
            else:
                print('Unknown output format {0}!'.format(output))
        except signalfx.signalflow.errors.ComputationAborted as e:
            print(e)
        except signalfx.signalflow.errors.ComputationFailed as e:
            print(e)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='SignalFlow Analytics interactive command-line client')
    parser.add_argument('-t', '--token', metavar='TOKEN',
                        help='session token')
    parser.add_argument('-x', '--execute', action='store_true',
                        help='force non-interactive mode')
    parser.add_argument('--api-endpoint', metavar='URL',
                        default='https://api.signalfx.com',
                        help='override API endpoint URL')
    parser.add_argument('--stream-endpoint', metavar='URL',
                        default='https://stream.signalfx.com',
                        help='override stream endpoint URL')
    parser.add_argument('-a', '--start', metavar='START',
                        default='-1m',
                        help='start timestamp or delta (default: -1m)')
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
                        default='live',
                        help='default output format')
    parser.add_argument('program', nargs='?', type=argparse.FileType('r'),
                        default=sys.stdin,
                        help='file to read program from (default: stdin)')
    TimezoneAction.add_to_parser(parser)
    options = parser.parse_args()

    params = {
        'start': options.start,
        'stop': options.stop,
        'resolution': options.resolution,
        'max_delay': options.max_delay,
        'output': options.output,
    }

    # Ensure that we have a session token.
    token = find_session_token(options)
    if not token:
        sys.stderr.write('No authentication token found.\n')
        return 1

    flow = signalfx.SignalFx(
        api_endpoint=options.api_endpoint,
        stream_endpoint=options.stream_endpoint).signalflow(token)
    try:
        if sys.stdin.isatty() and not options.execute:
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

    return 0

if __name__ == '__main__':
    sys.exit(main())
