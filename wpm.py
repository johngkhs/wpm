#!/usr/bin/env python

from __future__ import unicode_literals
from builtins import dict, str

import argparse
import curses
import locale
import io
import os
import signal
import sys
import textwrap
import time


CHARS_PER_WORD = 5.0
CURSOR_NOT_VISIBLE = 0
CURSOR_VERY_VISIBLE = 2
DEFAULT_LOCALE = ''
ENCODING = 'utf8'
ERROR_COLOR_ID = 1
FIFTY_MILLIS = 50
GETCH_KEY_DELETE = 127
GETCH_NO_INPUT = -1
INTRO_STR = 'Press any key to begin or Ctrl-C to exit'
OUTRO_STR = 'Press Ctrl-C to exit'
SECONDS_PER_MINUTE = 60.0


class ExitSuccess(Exception):
    def __init__(self):
        self.exit_code = os.EX_OK


class ExitFailure(Exception):
    def __init__(self, exit_code, msg):
        self.exit_code = exit_code
        self.msg = msg


class TerminalDimensions:
    def __init__(self, rows, columns):
        self.rows = rows
        self.columns = columns


def lookup_terminal_dimensions(screen):
    term_dimensions = screen.getmaxyx()
    rows = term_dimensions[0] - 1
    columns = term_dimensions[1]
    return TerminalDimensions(rows, columns)


def calculate_row_column(wrapped_terminal_lines, index):
    remaining_index = index
    for row, wrapped_line in enumerate(wrapped_terminal_lines):
        if remaining_index < len(wrapped_line):
            return (row, remaining_index)
        remaining_index -= len(wrapped_line)
    raise ExitFailure(os.EX_IOERR, 'Tried to access (row, column) out of terminal bounds')


def minutes_elapsed(seconds_elapsed):
    return (seconds_elapsed / SECONDS_PER_MINUTE)


def calculate_gross_wpm(num_correct_chars_typed, seconds_elapsed):
    words_typed = (num_correct_chars_typed / CHARS_PER_WORD)
    return int(words_typed / minutes_elapsed(seconds_elapsed))


def calculate_net_wpm(num_incorrect_chars_typed, num_correct_chars_typed, seconds_elapsed):
    gross_wpm = calculate_gross_wpm(num_correct_chars_typed, seconds_elapsed)
    net_wpm = gross_wpm - num_incorrect_chars_typed / minutes_elapsed(seconds_elapsed)
    return max(0, int(net_wpm))


def create_wpm_summary_str(num_incorrect_chars_typed, num_correct_chars_typed, seconds_elapsed):
    gross_wpm = calculate_gross_wpm(num_correct_chars_typed, seconds_elapsed)
    net_wpm = calculate_net_wpm(num_incorrect_chars_typed, num_correct_chars_typed, seconds_elapsed)
    return 'Time: {:02d}s Errors: {:03d} Wpm: {:03d}'.format(int(seconds_elapsed), num_incorrect_chars_typed, net_wpm)


def wrap_terminal_lines(input_str, term_dims):
    wrapped_terminal_lines = textwrap.wrap(input_str, term_dims.columns, drop_whitespace=False)[:term_dims.rows]
    wrapped_total_length = sum(len(line) for line in wrapped_terminal_lines)
    return (wrapped_terminal_lines, wrapped_total_length)


def draw_screen(screen, term_dims, input_str, error_char_indices, footer_str, cursor_index=None):
    screen.move(0, 0)
    screen.erase()
    wrapped_terminal_lines, wrapped_total_length = wrap_terminal_lines(input_str, term_dims)
    for row, wrapped_line in enumerate(wrapped_terminal_lines):
      screen.addstr(row, 0, wrapped_line.encode(ENCODING))
    screen.move(term_dims.rows, 0)
    screen.addstr(footer_str[:term_dims.columns - 1].encode(ENCODING))
    for error_char_index in error_char_indices:
        if error_char_index < wrapped_total_length:
            row, column = calculate_row_column(wrapped_terminal_lines, error_char_index)
            screen.addstr(row, column, input_str[error_char_index].encode(ENCODING), curses.color_pair(ERROR_COLOR_ID))
    if cursor_index is not None:
        row, column = calculate_row_column(wrapped_terminal_lines, cursor_index)
        screen.move(row, column)
    screen.refresh()


def is_typing_test_finished(input_str, term_dims, next_char_index, seconds_elapsed):
    wrapped_terminal_lines, wrapped_total_length = wrap_terminal_lines(input_str, term_dims)
    end_char_index = min(wrapped_total_length, len(input_str))
    return seconds_elapsed >= 60 or next_char_index >= end_char_index


def run_curses(screen, input_str):
    curses.start_color()
    curses.use_default_colors()
    curses.curs_set(CURSOR_VERY_VISIBLE)
    curses.init_pair(ERROR_COLOR_ID, curses.COLOR_BLACK, curses.COLOR_RED)
    locale.setlocale(locale.LC_ALL, DEFAULT_LOCALE)
    term_dims = lookup_terminal_dimensions(screen)
    next_char_index, error_char_indices = 0, []
    draw_screen(screen, term_dims, input_str, error_char_indices, INTRO_STR, cursor_index=next_char_index)
    user_input = screen.getch()
    start_time_seconds = time.time()
    screen.timeout(FIFTY_MILLIS)
    while True:
        if user_input == GETCH_NO_INPUT or user_input == curses.KEY_RESIZE:
            pass
        elif user_input == GETCH_KEY_DELETE or user_input == curses.KEY_BACKSPACE:
            prev_char_index = max(0, next_char_index - 1)
            if prev_char_index in error_char_indices:
                error_char_indices.remove(prev_char_index)
            next_char_index = prev_char_index
        else:
            correct_next_char = input_str[next_char_index]
            if user_input != ord(correct_next_char):
                error_char_indices.append(next_char_index)
            next_char_index += 1
        term_dims = lookup_terminal_dimensions(screen)
        seconds_elapsed = time.time() - start_time_seconds
        num_incorrect_chars_typed = len(error_char_indices)
        num_correct_chars_typed = next_char_index - num_incorrect_chars_typed
        wpm_summary_str = create_wpm_summary_str(num_incorrect_chars_typed, num_correct_chars_typed, seconds_elapsed)
        if is_typing_test_finished(input_str, term_dims, next_char_index, seconds_elapsed):
            curses.curs_set(CURSOR_NOT_VISIBLE)
            while True:
                term_dims = lookup_terminal_dimensions(screen)
                draw_screen(screen, term_dims, input_str, error_char_indices, '{} - {}'.format(OUTRO_STR, wpm_summary_str))
                user_input = screen.getch()
        draw_screen(screen, term_dims, input_str, error_char_indices, wpm_summary_str, cursor_index=next_char_index)
        user_input = screen.getch()


def readlines_from_file(input_filepath):
    try:
        input_file = io.open(input_filepath, 'r', encoding=ENCODING)
    except EnvironmentError:
        raise ExitFailure(os.EX_NOINPUT, '{}: No such file or directory'.format(input_filepath))
    with input_file:
      return input_file.readlines()


def concatenate_lines(lines):
    words = []
    for line in lines:
        words += line.replace('\t', ' ').rstrip().split()
    return ' '.join(words)


def change_stdin_to_terminal():
    terminal_stdin = open('/dev/tty')
    os.dup2(terminal_stdin.fileno(), 0)


def run():
    description = 'A command line words per minute test using a file or stdin'
    arg_parser = argparse.ArgumentParser(description=description)
    arg_parser.add_argument('input_filepath', nargs='?')
    args = arg_parser.parse_args()
    if sys.stdin.isatty() and not args.input_filepath:
        arg_parser.print_help()
        return os.EX_USAGE
    lines = readlines_from_file(args.input_filepath) if args.input_filepath else sys.stdin.readlines()
    input_str = concatenate_lines(lines)
    if not input_str:
        return os.EX_OK
    if not sys.stdin.isatty():
        change_stdin_to_terminal()
    return curses.wrapper(run_curses, input_str)


def main():
    def sigterm_handler(signal, frame):
        raise ExitSuccess()
    signal.signal(signal.SIGTERM, sigterm_handler)
    try:
        exit_code = run()
    except KeyboardInterrupt:
        exit_code = os.EX_OK
    except ExitSuccess as e:
        exit_code = e.exit_code
    except ExitFailure as e:
        sys.stderr.write(e.msg + '\n')
        exit_code = e.exit_code
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
