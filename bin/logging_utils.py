#                             Logging Utils
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
"""Different utilities that creates a logger module, available for the hole system"""
import logging
import os
from sys import stdout

# Default format to use when logging messages:
# <ACTUAL TIME> [<LEVEL NAME>]    <MESSAGE>
LOG_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s]\t%(message)s"

# Logger name that can be used globally to obtain this logger
LOGGER_NAME = r"dup-logger"


def get_logger() -> logging.Logger:
    """Generates (or returns) an existing logger from the system
    that should be used globally on this program.

    Returns:
        logging.Logger: the system logger
    """
    log = logging.getLogger(LOGGER_NAME)

    # as we have set no `basicConfig`, newly created loggers
    # will evaluate this to False. If it existed, then it will
    # have at least one handler
    if log.hasHandlers():
        return log

    formatter = logging.Formatter(LOG_DEFAULT_FORMAT)
    handler = logging.StreamHandler(stream=stdout)
    level = os.environ.get("LOG_LEVEL", "INFO")
    handler.setLevel(level)
    handler.setFormatter(formatter)

    log.addHandler(handler)
    log.setLevel(level)

    return log
