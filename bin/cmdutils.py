#                             CMD Utils
#                  Copyright (C) 2021 - Javinator9889
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#                   (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#               GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Different utilities that help running long commands, capture outputs, etc"""
import logging
import os
import re
import shlex
from string import Template
from subprocess import PIPE, STDOUT, Popen
from typing import MutableMapping


def is_blank(s: str) -> bool:
    """Checks if the given string is blank or not

    Args:
        s (str): string to check

    Returns:
        bool: self explanatory
    """
    if not isinstance(s, str):
        return False
    return not (s and s.strip())


def run(
    cmd: str,
    env: MutableMapping = None,
    log: logging.Logger = None,
    shell: bool = False,
) -> tuple[int, str]:
    """Runs the given command by using the `subprocess` module, wraps the
    output and prints it line by line while it's still running. When finished,
    returns the process return code. If `log` is defined, lines are printed
    directly but wrapped with it.

    Args:
        cmd (str): command to run. Notice that this command will be splitted
                   by using `shelx`. See: https://docs.python.org/3/library/shlex.html
                   for more information.
        env (MuttableMapping, optional): environment variables that will be
                                         substituted, if any. When not given, gets
                                         those variables from system environment.
                                         Defaults to None.
        log (logging.Logger, optional): log instance to use when outputting debug
                                        information or similar. If no specified, uses
                                        system logger. Defaults to None.
        shell (bool, optional): whether if the command should be run inside a shell
                                or can be executed "as is". Defaults to False

    Returns:
        tuple[int, str]: command return code and command output (stdout if all OK,
                         stderr if not)
    """
    if env is None:
        env = os.environ

    if log is None:
        info = lambda text: print(text, end="", flush=True)
    else:
        # if we are using logger, remove endings
        info = lambda text: log.info(text.strip())

    cmd = Template(cmd).safe_substitute(env)
    if not shell:
        cmd = shlex.split(cmd)

    output = []
    with Popen(
        cmd,
        stdout=PIPE,
        stderr=STDOUT,
        bufsize=1,
        universal_newlines=True,
        shell=shell,
    ) as proc:
        for line in proc.stdout:
            if not is_blank(line):
                output.append(line)
                info(line)

        ret = proc.wait()

    output = "".join(output)
    return ret, output


# currently, we only have one data pattern to hide data
# from MySQL commands, which outputs the password. The
# following set is created by tuples of two items in which
# the first one is the pattern and the second one is the
# substitution. This allows adding new options without
# the need to modify source code, just this constant
DATA_PATTERN = {
    (re.compile(r"\s{1}-p.*\s{1}"), r" -p******** "),
}


def print_command(cmd: str) -> str:
    """Prepares the given command for "safely" printing to console.
    This consists on removing sensitive information or similar.

    Args:
        cmd (str): command to print

    Returns:
        str: "safe" command
    """
    for pattern, substitution in DATA_PATTERN:
        cmd = pattern.sub(substitution, cmd)

    return cmd
