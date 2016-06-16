SignalFx SignalFlow™ Analytics interactive command-line
=======================================================

``signalflow`` is a command-line client for SignalFx SignalFlow Analytics. It
allows for executing, controlling and streaming live output from SignalFlow
Analytics computations, as well as batch non-streaming output.

For more information on the SignalFlow analytics language, visit the SignalFx
Developers documentation at https://developers.signalfx.com.

Installation
------------

To install, along with the required dependencies, simply use ``pip``:

.. code::

    $ pip install git+https://github.com/signalfx/signalflow-cli

Demo
----

|demo|

.. |demo| image:: https://asciinema.org/a/8g5vaxyjakol8onretxdqbfgv.png
         :target: https://asciinema.org/a/8g5vaxyjakol8onretxdqbfgv

Usage
-----

The ``signalflow`` command-line tool supports both interactive and
non-interactive operation modes. In interactive mode, it offers a prompt that
allows for setting computation parameters and executing SignalFlow programs
while visualizing their streaming output in real-time. The default display
shows the live data, with a spark line of the last 10 values, for each received
time series. CSV output and graph output can also be optained by setting the
`.output` parameter (see below "Interactive mode usage").

In non-interactive mode, ``signalflow`` reads the SignalFlow program text
(either from stdin or from a file) and outputs the results the format specified
by the ``--output`` command-line flag. By default, this uses the same live data
display as the interactive prompt. The available output modes are:

- ``csv``; outputs the data in CSV format. The first column is a millisecond
  timestamp; other columns contain the value of each output time series for
  each of those times.

  This output will keep streaming unless a fixed stopped time has been
  specified (which can be either in the past or in the future).

- ``graph``; generates CSV data and renders it as a graph in a window.

- ``live``; shows the same live display as in interactive mode, just without
  the prompt around it. Computation parameters should be set via the
  appropriate command-line flags as necessary.


Finally, the graphing can also be used from the provided standalone utility
``csv-to-plot``, which reads CSV data from a file (or stdin) and renders the
graph. Using ``--output graph`` is the same as piping the output of ``--output
csv`` into ``csv-to-plot``:

.. code::

    $ signalflow --token <session token> --start=-15m --stop=-1m \
        --output=graph < program.txt
    $ signalflow --token <session token> --start=-15m --stop=-1m \
        --output=csv < program.txt | csv-to-plot

Interactive mode usage
^^^^^^^^^^^^^^^^^^^^^^

.. code::

    $ signalflow --token <session token>

After a greeting header, you should see the prompt ``> ``. You can then enter a
SignalFlow program (even across multiple lines) and press ``^D`` (Control-D) to
execute the program and visualize the results. Press ``^C`` at any time to
interrupt the stream, and again to exit the client.

Computation parameters can be listed with the ``.`` command:

.. code::

    > .
    {'max_delay': None,
     'output': 'live',
     'resolution': None,
     'start': '-1m',
     'stop': None}

You can change one of those values with ``.<parameter> <value>``:

.. code::

    > .start -15m
    > .stop -1m
    > .
    {'max_delay': None,
     'output': 'live',
     'resolution': None,
     'start': '-15m',
     'stop': '-1m'}

To reset a parameter to ``None`` (which usually means "auto"), use
``.<parameter>``:

.. code::

    > .stop
    > .
    {'max_delay': None,
     'output': 'live',
     'resolution': None,
     'start': '-15m',
     'stop': None}


Obtaining your token
--------------------

To obtain a session token, simply authenticate against the SignalFx API's
``/v2/session`` endpoint as described in the API documentation:
https://developers.signalfx.com/docs/session. If you don't pass the ``--token``
parameter, the SignalFlow CLI will prompt for your username and password and
obtain a token for you.
