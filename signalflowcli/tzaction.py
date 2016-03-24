#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016 SignalFx, Inc. All Rights Reserved.

import argparse
import pytz


class TimezoneAction(argparse.Action):

    DEFAULT_TZ = pytz.timezone('US/Pacific')

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(TimezoneAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, pytz.timezone(values))

    @staticmethod
    def add_to_parser(parser):
        parser.add_argument('--timezone', metavar='TZ',
                            action=TimezoneAction,
                            default=TimezoneAction.DEFAULT_TZ,
                            help=('set display timezone (default: {0})'
                                  .format(TimezoneAction.DEFAULT_TZ.zone)))
