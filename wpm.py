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
    def __init__(self, screen):
        self.update(screen)

    def update(self, screen):
        term_dimensions = screen.getmaxyx()
        self.rows = term_dimensions[0] - 1
        self.columns = term_dimensions[1]


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
    return 'Gross WPM: {} Errors: {} Net Wpm: {}'.format(gross_wpm, num_incorrect_chars_typed, net_wpm)


def get_row_column(index, columns):
    return (index / columns, index % columns)


def draw_screen(screen, term_dims, input_str, color_id, colored_indexes, cursor_index, footer_str):
    screen.move(0, 0)
    screen.erase()
    wrapped_lines = textwrap.wrap(input_str, term_dims.columns)
    for row, wrapped_line in enumerate(wrapped_lines[:term_dims.rows]):
        screen.addstr(row, 0, wrapped_line)
    screen.move(term_dims.rows, 0)
    screen.addstr(footer_str[:term_dims.columns - 1])
    for colored_index in colored_indexes:
        colored_row, colored_column = get_row_column(colored_index, term_dims.columns)
        screen.addch(colored_row, colored_column, input_str[colored_index], curses.color_pair(color_id))
    cursor_row, cursor_column = get_row_column(cursor_index, term_dims.columns)
    screen.move(cursor_row, cursor_column)
    screen.refresh()


def run_curses(screen, input_str):
    curses.use_default_colors()
    VERY_VISIBLE = 2
    curses.curs_set(VERY_VISIBLE)
    ERROR_COLOR_ID = 1
    DEFAULT_BACKGROUND_COLOR = -1
    curses.init_pair(ERROR_COLOR_ID, curses.COLOR_RED, DEFAULT_BACKGROUND_COLOR)
    locale.setlocale(locale.LC_ALL, '')
    term_dims = TerminalDimensions(screen)
    incorrect_char_indexes = []
    next_char_index = 0
    draw_screen(screen, term_dims, input_str, ERROR_COLOR_ID, incorrect_char_indexes, next_char_index, 'Press any key to begin or Ctrl-C to exit')
    user_input = screen.getch()
    start_time_seconds = time.time()
    FIFTY_MILLIS = 50
    screen.timeout(FIFTY_MILLIS)
    NO_INPUT = -1
    KEY_DELETE = 127
    while True:
        try:
            if user_input == NO_INPUT:
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
            term_dims.update(screen)
            seconds_elapsed = time.time() - start_time_seconds
            num_incorrect_chars_typed = len(incorrect_char_indexes)
            num_correct_chars_typed = next_char_index - num_incorrect_chars_typed
            wpm_summary_str = create_wpm_summary_str(num_incorrect_chars_typed, num_correct_chars_typed, seconds_elapsed)
            draw_screen(screen, term_dims, input_str, ERROR_COLOR_ID, incorrect_char_indexes, next_char_index, wpm_summary_str)
            typing_test_finished = (next_char_index == len(input_str) or seconds_elapsed >= 60)
            if typing_test_finished:
                screen.timeout(0)
                draw_screen(screen, term_dims, input_str, ERROR_COLOR_ID, incorrect_char_indexes, next_char_index, 'Press any key to exit') # todo fix
                screen.getch()
                return os.EX_OK
            user_input = screen.getch()
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


def concatenate_lines(lines):
    words = []
    for line in lines:
        words += line.replace('\t', ' ').rstrip().split()
    return ' '.join(words)


def run():
    description = 'A command line words per minute test using a file or stdin'
    arg_parser = argparse.ArgumentParser(description=description)
    arg_parser.add_argument('input_filepath', nargs='?')
    args = arg_parser.parse_args()
    if sys.stdin.isatty() and not args.input_filepath:
        arg_parser.print_help()
        return os.EX_USAGE
    lines = readlines_from_file_or_stdin(args.input_filepath)
    input_str = concatenate_lines(lines)
    return curses.wrapper(run_curses, input_str)


def main():
    def sigterm_handler(signal, frame):
        raise ExitSuccess()
    signal.signal(signal.SIGTERM, sigterm_handler)
    try:
        exit_code = run()
    except ExitSuccess as e:
        exit_code = e.exit_code
    except ExitFailure as e:
        sys.stderr.write(e.msg + '\n')
        exit_code = e.exit_code
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
