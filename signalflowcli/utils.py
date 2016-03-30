#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2016 SignalFx, Inc. All Rights Reserved.

from __future__ import print_function
import sys


def message(s):
    """Display the given message string with no new line and flush
    immediately."""
    print(s, end='')
    sys.stdout.flush()
