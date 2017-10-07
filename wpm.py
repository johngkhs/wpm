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


class TypingProgress:
    def __init__(self, input_str):
        self.input_str = input_str
        self.input_str_len = len(input_str)
        self.next_char_index = 0

    def check_user_input(self, user_input):
        KEY_DELETE = 127
        if user_input == KEY_DELETE or user_input == curses.KEY_BACKSPACE:
            self.next_char_index = max(0, self.next_char_index - 1)
        elif user_input == ord(self.input_str[self.next_char_index]):
            self.next_char_index = min(self.input_str_len - 1, self.next_char_index + 1)


def get_cursor_position(typing_progress, cols):
    chars_left = typing_progress.next_char_index
    for row, wrapped_line in enumerate(wrap(typing_progress.input_str, cols)):
        chars_left -= len(wrapped_line)
        if chars_left < 0:
            return (row, chars_left + len(wrapped_line))
    raise ExitFailure('Cursor position fell off the end of the screen')


def draw_screen(screen, term_dims, typing_progress):
    screen.move(0, 0)
    screen.erase()
    row = 0
    for wrapped_line in wrap(typing_progress.input_str, term_dims.cols):
        if row == term_dims.rows:
            break
        screen.addstr(row, 0, wrapped_line)
        row += 1
    cursor_row, cursor_col = get_cursor_position(typing_progress, term_dims.cols)
    screen.move(cursor_row, cursor_col)
    screen.refresh()


def wrap(line, cols):
    return [line[i:i + cols] for i in range(0, len(line), cols)]


def run_curses(screen, input_str):
    curses.use_default_colors()
    VERY_VISIBLE = 2
    curses.curs_set(VERY_VISIBLE)
    screen.timeout(50)
    term_dims = TerminalDimensions(screen)
    typing_progress = TypingProgress(input_str)
    while True:
        try:
            term_dims.update(screen)
            draw_screen(screen, term_dims, typing_progress)
            user_input = screen.getch()
            typing_progress.check_user_input(user_input)
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
