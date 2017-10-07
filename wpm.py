#!/usr/bin/env python

import argparse
import curses
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


def draw_screen(screen, next_char_index, term_dims, input_str):
    screen.move(0, 0)
    screen.erase()
    row = 0
    for wrapped_line in wrap(input_str, term_dims.cols):
        if row == term_dims.rows:
            break
        screen.addstr(row, 0, wrapped_line)
        row += 1
    screen.move(0, next_char_index)
    screen.refresh()


def wrap(line, cols):
    return [line[i:i + cols] for i in range(0, len(line), cols)]


def run_curses(screen, input_str):
    curses.use_default_colors()
    VERY_VISIBLE = 2
    curses.curs_set(VERY_VISIBLE)
    screen.timeout(50)
    term_dims = TerminalDimensions(screen)
    next_char_index = 0
    while True:
        try:
            term_dims.update(screen)
            draw_screen(screen, next_char_index, term_dims, input_str)
            user_input = screen.getch()
            if user_input == ord(input_str[next_char_index]):
                next_char_index += 1
            else:
                pass
        except KeyboardInterrupt:
            return os.EX_OK


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


def concat_lines(lines):
    words = []
    for line in lines:
        words += line.replace('\t', ' ').rstrip().split()
    return ' '.join(words)


def run(args):
    description = 'A command line words per minute test'
    arg_parser = argparse.ArgumentParser(description=description)
    arg_parser.add_argument('input_filepath', nargs='?')
    args = arg_parser.parse_args()
    if sys.stdin.isatty() and not args.input_filepath:
        arg_parser.print_help()
        return os.EX_USAGE
    lines = readlines_from_file_or_stdin(args.input_filepath)
    input_str = concat_lines(lines)
    return curses.wrapper(run_curses, input_str)


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
