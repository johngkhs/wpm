#!/usr/bin/env python

import argparse
import curses
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
        self.cols = term_dimensions[1]


class WpmCalculator:
    def __init__(self, typing_progress, time_elapsed):
        self.CHARS_PER_WORD = 5.0
        SEC_PER_MIN = 60.0
        self.minutes_elapsed = time_elapsed / SEC_PER_MIN
        self.typing_progress = typing_progress

    def compute_wpm_str(self):
        num_incorrect_chars_typed = self.typing_progress.get_num_incorrect_chars_typed()
        return 'Gross WPM: {} Errors: {} Net Wpm: {}'.format(self._calculate_gross_wpm(), num_incorrect_chars_typed, self._calculate_net_wpm())

    def _calculate_gross_wpm(self):
        words_typed = (self.typing_progress.get_num_correct_chars_typed() / self.CHARS_PER_WORD)
        return int(words_typed / self.minutes_elapsed)

    def _calculate_net_wpm(self):
        return max(0, int(self._calculate_gross_wpm() - (self.typing_progress.get_num_incorrect_chars_typed() / self.minutes_elapsed)))


class TypingProgress:
    def __init__(self, input_str):
        self.input_str = input_str
        self.input_str_len = len(input_str)
        self.incorrect_char_indexes = []
        self.next_char_index = 0

    def get_num_incorrect_chars_typed(self):
        return len(self.incorrect_char_indexes)

    def get_num_correct_chars_typed(self):
        return self.next_char_index - self.get_num_incorrect_chars_typed()

    def on_user_input(self, user_input):
        KEY_DELETE = 127
        if user_input == KEY_DELETE or user_input == curses.KEY_BACKSPACE:
            if self.next_char_index in self.incorrect_char_indexes:
                self.incorrect_char_indexes.remove(self.next_char_index)
            self.next_char_index = max(0, self.next_char_index - 1)
        else:
            next_char_expected = self.input_str[self.next_char_index]
            if user_input != ord(next_char_expected):
                self.incorrect_char_indexes.append(self.next_char_index)
            self.next_char_index += 1
            if self.next_char_index == self.input_str_len:
                return True
        return False


def get_cursor_position(typing_progress, cols):
    chars_left = typing_progress.next_char_index
    for row, wrapped_line in enumerate(textwrap.wrap(typing_progress.input_str, cols)):
        chars_left -= len(wrapped_line)
        if chars_left < 0:
            return (row, chars_left + len(wrapped_line))
    raise ExitFailure('Cursor position fell off the end of the screen')


def draw_screen(screen, term_dims, typing_progress, start_time, curr_time):
    screen.move(0, 0)
    screen.erase()
    row = 0
    for wrapped_line in textwrap.wrap(typing_progress.input_str, term_dims.cols):
        if row == term_dims.rows:
            break
        screen.addstr(row, 0, wrapped_line)
        row += 1
    screen.move(term_dims.rows, 0)
    if start_time:
        time_elapsed = (curr_time - start_time)
        wpm_calculator = WpmCalculator(typing_progress, time_elapsed)
        screen.addstr(wpm_calculator.compute_wpm_str())
    else:
        screen.addstr(' Press any key to start, or Ctrl-C to exit'[:term_dims.cols - 1])
    cursor_row, cursor_col = get_cursor_position(typing_progress, term_dims.cols)
    screen.move(cursor_row, cursor_col)
    screen.refresh()


def run_curses(screen, input_str):
    curses.use_default_colors()
    VERY_VISIBLE = 2
    curses.curs_set(VERY_VISIBLE)
    NO_INPUT = -1
    screen.timeout(50)
    term_dims = TerminalDimensions(screen)
    typing_progress = TypingProgress(input_str)
    start_time = None
    while True:
        try:
            term_dims.update(screen)
            draw_screen(screen, term_dims, typing_progress, start_time, time.time())
            user_input = screen.getch()
            if user_input == NO_INPUT:
                continue
            if not start_time:
                start_time = time.time()
            if typing_progress.on_user_input(user_input):
                screen.timeout(0)
                # press any key to continue
                screen.getch()
                return os.EX_OK
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
