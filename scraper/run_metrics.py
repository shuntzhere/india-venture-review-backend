"""Whole-run CPU and wall time. Do not sum overlapping thread CPU intervals."""
import time
from contextlib import contextmanager


def start_run(summary):
    summary['_clock'] = (time.monotonic(), time.process_time())
    summary['stages'] = {}


def finish_run(summary):
    wall, cpu = summary.pop('_clock', (time.monotonic(), time.process_time()))
    summary['duration_ms'] = max(0, round((time.monotonic()-wall)*1000))
    summary['cpu_ms'] = max(0, round((time.process_time()-cpu)*1000))


@contextmanager
def stage(summary, name):
    wall, cpu = time.monotonic(), time.process_time()
    try:
        yield
    finally:
        summary['stages'][name] = {'wall_ms': max(0, round((time.monotonic()-wall)*1000)),
                                  'cpu_ms': max(0, round((time.process_time()-cpu)*1000))}
