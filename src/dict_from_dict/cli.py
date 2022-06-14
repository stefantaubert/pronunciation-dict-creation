import argparse
import importlib.metadata
import logging
import sys
from argparse import ArgumentParser
from logging import getLogger
from typing import Callable, Generator, List, Tuple

from dict_from_dict.main import get_app_try_add_vocabulary_from_pronunciations_parser

__version__ = importlib.metadata.version("dict-from-dict")

INVOKE_HANDLER_VAR = "invoke_handler"


Parsers = Generator[Tuple[str, str, Callable], None, None]


def formatter(prog):
  return argparse.ArgumentDefaultsHelpFormatter(prog, max_help_position=40)


def _init_parser():
  main_parser = ArgumentParser(formatter_class=formatter)
  main_parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
  method = get_app_try_add_vocabulary_from_pronunciations_parser(main_parser)
  main_parser.set_defaults(**{
      INVOKE_HANDLER_VAR: method,
  })

  return main_parser


def configure_logger() -> None:
  loglevel = logging.DEBUG if __debug__ else logging.INFO
  main_logger = getLogger()
  main_logger.setLevel(loglevel)
  main_logger.manager.disable = logging.NOTSET
  if len(main_logger.handlers) > 0:
    console = main_logger.handlers[0]
  else:
    console = logging.StreamHandler()
    main_logger.addHandler(console)

  logging_formatter = logging.Formatter(
    '[%(asctime)s.%(msecs)03d] (%(levelname)s) %(message)s',
    '%Y/%m/%d %H:%M:%S',
  )
  console.setFormatter(logging_formatter)
  console.setLevel(loglevel)


def parse_args(args: List[str]):
  configure_logger()
  logger = getLogger(__name__)
  logger.debug("Received args:")
  logger.debug(args)
  parser = _init_parser()
  if len(args) == 0:
    parser.print_help()
    return

  received_args = parser.parse_args(args)
  params = vars(received_args)

  if INVOKE_HANDLER_VAR in params:
    invoke_handler: Callable[[ArgumentParser], None] = params.pop(INVOKE_HANDLER_VAR)
    invoke_handler(received_args)
  else:
    parser.print_help()


def run():
  arguments = sys.argv[1:]
  parse_args(arguments)


if __name__ == "__main__":
  run()
