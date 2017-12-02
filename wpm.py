#!/usr/bin/env python

import argparse
import curses
import locale
import os
import signal
import sys
import textwrap
import time


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


def calculate_terminal_dimensions(screen):
    term_dimensions = screen.getmaxyx()
    rows = term_dimensions[0] - 1
    columns = term_dimensions[1]
    return TerminalDimensions(rows, columns)


def get_row_column(wrapped_terminal_lines, index):
    remaining_index = index
    for row, wrapped_line in enumerate(wrapped_terminal_lines):
        if remaining_index < len(wrapped_line):
            return (row, remaining_index)
        remaining_index -= len(wrapped_line)
    raise ExitFailure(os.EX_IOERR, 'Tried to access (row, column) out of terminal bounds')


def minutes_elapsed(seconds_elapsed):
    SECONDS_PER_MINUTE = 60.0
    return (seconds_elapsed / SECONDS_PER_MINUTE)


def calculate_gross_wpm(num_correct_chars_typed, seconds_elapsed):
    CHARS_PER_WORD = 5.0
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


def draw_screen(screen, term_dims, input_str, color_id, colored_indexes, footer_str, cursor_index=None):
    screen.move(0, 0)
    screen.erase()
    wrapped_terminal_lines, wrapped_total_length = wrap_terminal_lines(input_str, term_dims)
    for row, wrapped_line in enumerate(wrapped_terminal_lines):
        screen.addstr(row, 0, wrapped_line)
    screen.move(term_dims.rows, 0)
    screen.addstr(footer_str[:term_dims.columns - 1])
    for colored_index in colored_indexes:
        if colored_index < wrapped_total_length:
            row, column = get_row_column(wrapped_terminal_lines, colored_index)
            screen.addch(row, column, input_str[colored_index], curses.color_pair(color_id))
    if cursor_index is not None:
        row, column = get_row_column(wrapped_terminal_lines, cursor_index)
        screen.move(row, column)
    screen.refresh()


def is_typing_test_finished(input_str, term_dims, next_char_index, seconds_elapsed):
    wrapped_terminal_lines, wrapped_total_length = wrap_terminal_lines(input_str, term_dims)
    end_char_index = min(wrapped_total_length, len(input_str))
    if seconds_elapsed >= 60:
        return True
    elif next_char_index >= end_char_index:
        return True
    else:
        return False


def run_curses(screen, input_str):
    curses.use_default_colors()
    VERY_VISIBLE = 2
    curses.curs_set(VERY_VISIBLE)
    ERROR_COLOR_ID = 1
    DEFAULT_BACKGROUND_COLOR = -1
    curses.init_pair(ERROR_COLOR_ID, curses.COLOR_RED, DEFAULT_BACKGROUND_COLOR)
    locale.setlocale(locale.LC_ALL, '')
    term_dims = calculate_terminal_dimensions(screen)
    incorrect_char_indexes = []
    next_char_index = 0
    START_STR = 'Press any key to begin or Ctrl-C to exit'
    draw_screen(screen, term_dims, input_str, ERROR_COLOR_ID, incorrect_char_indexes, START_STR, cursor_index=next_char_index)
    user_input = screen.getch()
    start_time_seconds = time.time()
    FIFTY_MILLIS = 50
    screen.timeout(FIFTY_MILLIS)
    NO_INPUT = -1
    KEY_DELETE = 127
    while True:
        if user_input == NO_INPUT or user_input == curses.KEY_RESIZE:
            pass
        elif user_input == KEY_DELETE or user_input == curses.KEY_BACKSPACE:
            prev_char_index = max(0, next_char_index - 1)
            if prev_char_index in incorrect_char_indexes:
                incorrect_char_indexes.remove(prev_char_index)
            next_char_index = prev_char_index
        else:
            correct_next_char = input_str[next_char_index]
            if user_input != ord(correct_next_char):
                incorrect_char_indexes.append(next_char_index)
            next_char_index += 1
        term_dims = calculate_terminal_dimensions(screen)
        seconds_elapsed = time.time() - start_time_seconds
        num_incorrect_chars_typed = len(incorrect_char_indexes)
        num_correct_chars_typed = next_char_index - num_incorrect_chars_typed
        wpm_summary_str = create_wpm_summary_str(num_incorrect_chars_typed, num_correct_chars_typed, seconds_elapsed)
        if is_typing_test_finished(input_str, term_dims, next_char_index, seconds_elapsed):
            exit_str = 'Press Ctrl-C to exit - {}'.format(wpm_summary_str)
            NOT_VISIBLE = 0
            curses.curs_set(NOT_VISIBLE)
            while True:
                term_dims = calculate_terminal_dimensions(screen)
                draw_screen(screen, term_dims, input_str, ERROR_COLOR_ID, incorrect_char_indexes, exit_str)
                user_input = screen.getch()
        draw_screen(screen, term_dims, input_str, ERROR_COLOR_ID, incorrect_char_indexes, wpm_summary_str, cursor_index=next_char_index)
        user_input = screen.getch()


def readlines_from_file(input_filepath):
    try:
        input_file = open(input_filepath, 'r')
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
