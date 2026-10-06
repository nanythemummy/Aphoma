import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from UI.BuildConsole import ConsoleStream


class DummyWidget:
    def __init__(self):
        self.text = ""

    def configure(self, *args, **kwargs):
        pass

    def insert(self, *args):
        self.text += args[1]

    def yview(self, *args):
        pass

    def after(self, _delay, callback, *args):
        callback(*args)


def test_console_stream_writes_to_widget_and_underlying_stream():
    widget = DummyWidget()
    underlying = io.StringIO()
    stream = ConsoleStream(widget, underlying)

    stream.write("hello from stdout")
    stream.flush()

    assert widget.text == "hello from stdout"
    assert underlying.getvalue() == "hello from stdout"


def test_console_stream_normalizes_line_endings():
    widget = DummyWidget()
    underlying = io.StringIO()
    stream = ConsoleStream(widget, underlying)

    stream.write("line one\r\nline two\rline three")
    stream.flush()

    assert widget.text == "line one\nline two\nline three"
    assert underlying.getvalue() == "line one\r\nline two\rline three"
