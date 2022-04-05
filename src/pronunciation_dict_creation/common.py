from collections import OrderedDict
from logging import getLogger
from pathlib import Path
from pronunciation_dict_parser.core.parser import PronunciationDict
from pronunciation_dict_parser.core.types import Symbol
import argparse
from argparse import ArgumentParser
from multiprocessing import cpu_count
from dataclasses import dataclass
from typing import List, Literal, Optional, Set, Tuple
from pronunciation_dict_parser import PronunciationDict, Symbol, Word, Pronunciations
from ordered_set import OrderedSet
from pronunciation_dict_creation.argparse_helper import get_optional, parse_codec, parse_positive_integer


DEFAULT_ENCODING = "UTF-8"
DEFAULT_N_JOBS = cpu_count()
DEFAULT_N_FILE_CHUNKSIZE = 1000
DEFAULT_MAXTASKSPERCHILD = None


PROG_SYMBOL_SEP = " "
PROG_WORD_SEP = "  "
PROG_INCLUDE_COUNTER = False
PROG_EMPTY_SYMBOL = ""
PROG_ONLY_FIRST = False
PROG_ENCODING = "UTF-8"


@dataclass()
class DefaultParameters():
  vocabulary: OrderedSet[Word]
  consider_annotations: bool
  annotation_split_symbol: Optional[str]
  # handle_duplicates: Literal["ignore", "add", "replace"]
  split_on_hyphen: bool
  trim_symbols: Set[Symbol]
  n_jobs: int
  maxtasksperchild: Optional[int]
  chunksize: int


def get_dictionary(pronunciations_to_i: Pronunciations, words_to_lookup: OrderedSet[Word]) -> Tuple[PronunciationDict, OrderedSet[Word]]:
  resulting_dict = OrderedDict()
  unresolved_words = OrderedSet()
  for i, pronunciations in pronunciations_to_i:
    word = words_to_lookup[i]
    if pronunciations is None:
      unresolved_words.add(word)
      continue
    assert word not in resulting_dict
    resulting_dict[word] = pronunciations
  return resulting_dict, unresolved_words


def update_dictionary(target_dictionary: PronunciationDict, pronunciations_to_i: Pronunciations, words_to_lookup: OrderedSet[Word], handle_duplicates: Literal["ignore", "add", "replace"]) -> OrderedSet[Word]:
  unresolved_words = OrderedSet()
  for i, pronunciations in pronunciations_to_i:
    word = words_to_lookup[i]
    if pronunciations is None:
      unresolved_words.add(unresolved_words)
      continue
    if handle_duplicates == "ignore":
      assert word not in target_dictionary
      target_dictionary[word] = pronunciations
    elif handle_duplicates == "replace":
      target_dictionary[word] = pronunciations
    elif handle_duplicates == "add":
      if word not in target_dictionary:
        target_dictionary[word] = pronunciations
      else:
        target_dictionary[word].update(pronunciations)
    else:
      assert False
  return unresolved_words


DEFAULT_PUNCTUATION = list(OrderedSet(sorted((
  "!", "\"", "#", "$", "%", "&", "'", "(", ")", "*", "+", ",", "-", ".", "/", ":", ";", "<", "=", ">", "?", "@", "[", "\\", "]", "{", "}", "~", "`",
  "、", "。", "？", "！", "：", "；", "।", "¿", "¡", "【", "】", "，", "…", "‥", "「", "」", "『", "』", "〝", "〟", "″", "⟨", "⟩", "♪", "・", "‹", "›", "«", "»", "～", "′", "“", "”"
))))


def add_encoding_argument(parser: ArgumentParser, variable: str, help_str: str) -> None:
  parser.add_argument(variable, type=parse_codec, metavar='CODEC',
                      help=help_str + "; see all available codecs at https://docs.python.org/3.8/library/codecs.html#standard-encodings", default=DEFAULT_ENCODING)


def add_n_jobs_argument(parser: ArgumentParser) -> None:
  parser.add_argument("-j", "--n-jobs", metavar='N', type=int,
                      choices=range(1, cpu_count() + 1), default=DEFAULT_N_JOBS, help="amount of parallel cpu jobs")


def add_chunksize_argument(parser: ArgumentParser, target: str = "words", default: int = DEFAULT_N_FILE_CHUNKSIZE) -> None:
  parser.add_argument("-c", "--chunksize", type=parse_positive_integer, metavar="NUMBER",
                      help=f"amount of {target} to chunk into one job", default=default)


def add_maxtaskperchild_argument(parser: ArgumentParser) -> None:
  parser.add_argument("-m", "--maxtasksperchild", type=get_optional(parse_positive_integer), metavar="NUMBER",
                      help="amount of tasks per child", default=DEFAULT_MAXTASKSPERCHILD)


class ConvertToOrderedSetAction(argparse._StoreAction):
  def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: Optional[List], option_string: Optional[str] = None):
    if values is not None:
      values = OrderedSet(values)
    super().__call__(parser, namespace, values, option_string)


def to_text(pronunciation_dict: PronunciationDict, word_pronunciation_sep: Symbol = PROG_WORD_SEP, symbol_sep: Symbol = PROG_SYMBOL_SEP, include_counter: bool = PROG_INCLUDE_COUNTER, only_first_pronunciation: bool = PROG_ONLY_FIRST, empty_symbol: Symbol = PROG_EMPTY_SYMBOL) -> None:
  dict_content = ""
  for word, pronunciations in pronunciation_dict.items():
    for counter, pronunciation in enumerate(pronunciations):
      if len(pronunciation) == 0 and len(empty_symbol) > 0:
        pronunciation = tuple(empty_symbol)
      counter_str = f"({counter})" if include_counter and counter > 0 else ""
      pron = symbol_sep.join(pronunciation)
      line = f"{word}{counter_str}{word_pronunciation_sep}{pron}\n"
      dict_content += line
      if only_first_pronunciation:
        break
  dict_content = dict_content.rstrip("\n")
  return dict_content


def save_dict(pronunciation_dict: PronunciationDict, path: Path, word_pronunciation_sep: Symbol = PROG_WORD_SEP, symbol_sep: Symbol = PROG_SYMBOL_SEP, include_counter: bool = PROG_INCLUDE_COUNTER, only_first_pronunciation: bool = PROG_ONLY_FIRST, empty_symbol: Symbol = PROG_EMPTY_SYMBOL, encoding: str = PROG_ENCODING) -> bool:
  dict_content = to_text(pronunciation_dict, word_pronunciation_sep, symbol_sep,
                         include_counter, only_first_pronunciation, empty_symbol)
  path.parent.mkdir(parents=True, exist_ok=True)
  try:
    path.write_text(dict_content, encoding)
  except Exception as ex:
    logger = getLogger(__name__)
    logger.error("Dictionary couldn't be written.")
    return False
  return True
