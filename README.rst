SignalFx SignalFlow™ Analytics interactive command-line
=======================================================

`signalflow` is a command-line client for SignalFx SignalFlow Analytics. It
allows for executing, controlling and streaming live output from SignalFlow
Analytics computations, as well as batch non-streaming output.

Requirements
------------

To install the requirements, simply use ``pip``:

.. code::

    $ pip install --user -r requirements.txt

Usage
-----

.. code::

    $ signalflow --token <API token>

You can then enter a SignalFlow program (even across multiple lines), then
press ``^D`` (Control-D) to execute the program and visualize the results.
Press ``^C`` at any time to interrupt the stream, and again to exit the client.

Obtaining your token
--------------------

To obtain an API token, simply authenticate against the SignalFx API's
``/session`` endpoint as described in the API documentation:
https://developers.signalfx.com/docs/session.
