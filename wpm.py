#!/usr/bin/env python

import argparse
import os
import signal
import sys


class ExitSuccess(Exception):
    def __init__(self):
        self.exit_code = os.EX_OK


class ExitFailure(Exception):
    def __init__(self, exit_code, msg):
        self.exit_code = exit_code
        self.msg = msg


class TerminalDimensions:
    def __init__(self, screen):
        self.update(screen)

    def update(self, screen):
        term_dimensions = screen.getmaxyx()
        self.rows = term_dimensions[0] - 1
        self.cols = term_dimensions[1]


def run_curses(lines):
    print(lines)


def readlines_from_file_or_stdin(input_filepath):
    if input_filepath:
        try:
            input_file = open(input_filepath, 'r')
        except EnvironmentError:
            raise ExitFailure(os.EX_NOINPUT, '{}: No such file or directory'.format(input_filepath))
        with input_file:
            return input_file.readlines()
    else:
        return sys.stdin.readlines()


def run(args):
    description = 'A command line words per minute test'
    arg_parser = argparse.ArgumentParser(description=description)
    arg_parser.add_argument('input_filepath', nargs='?')
    args = arg_parser.parse_args()
    if sys.stdin.isatty() and not args.input_filepath:
        arg_parser.print_help()
        return os.EX_USAGE
    lines = readlines_from_file_or_stdin(args.input_filepath)
    return run_curses(lines)


def main():
    def sigterm_handler(signal, frame):
        raise ExitSuccess()
    signal.signal(signal.SIGTERM, sigterm_handler)
    try:
        exit_code = run(sys.argv[1:])
    except ExitSuccess as e:
        exit_code = e.exit_code
    except ExitFailure as e:
        sys.stderr.write(e.msg + '\n')
        exit_code = e.exit_code
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
