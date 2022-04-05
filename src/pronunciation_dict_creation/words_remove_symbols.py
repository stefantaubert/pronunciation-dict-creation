from argparse import ArgumentParser
from functools import partial
from logging import getLogger
from multiprocessing.pool import Pool
from pathlib import Path
import symbol
from typing import Literal
from pronunciation_dict_parser import PronunciationDict, Symbol
from ordered_set import OrderedSet
from pronunciation_dict_creation.argparse_helper import parse_existing_file, parse_non_empty, parse_path
from pronunciation_dict_creation.common import ConvertToOrderedSetAction, DEFAULT_PUNCTUATION, PROG_ENCODING, add_chunksize_argument, save_dict
from pronunciation_dict_parser import parse_dictionary_from_txt

from tempfile import gettempdir
from argparse import ArgumentParser
from logging import getLogger
from pathlib import Path
from tqdm import tqdm
from functools import partial
from multiprocessing.pool import Pool
from typing import Optional, Set, Tuple
from pronunciation_dict_parser import PronunciationDict, Symbol, Word, Pronunciations, Pronunciation
from ordered_set import OrderedSet
from pronunciation_dict_creation.argparse_helper import get_optional, parse_existing_file, parse_non_empty_or_whitespace, parse_path
from pronunciation_dict_creation.common import ConvertToOrderedSetAction, DEFAULT_PUNCTUATION, DefaultParameters, PROG_ENCODING, add_chunksize_argument, add_encoding_argument, add_maxtaskperchild_argument, add_n_jobs_argument, get_dictionary, save_dict
from pronunciation_dict_parser import parse_dictionary_from_txt


def get_words_remove_symbols_parser(parser: ArgumentParser):
  default_removed_out = Path(gettempdir()) / "removed-words.txt"
  parser.description = "Remove symbols from words. If all symbols of a word will be removed, the word will be taken out of the dictionary."
  parser.add_argument("dictionaries", metavar='dictionaries', type=parse_existing_file, nargs="+",
                      help="dictionary files", action=ConvertToOrderedSetAction)
  parser.add_argument("--symbols", type=str, metavar='SYMBOL', nargs='+',
                      help="remove these symbols from the pronunciations", action=ConvertToOrderedSetAction, default=DEFAULT_PUNCTUATION)
  parser.add_argument("--mode", type=str, choices=["all", "start", "end", "both"],
                      help="mode to remove the symbols: all = on all locations; start = only from start; end = only from end; both = start + end", default="both")
  # parser.add_argument("--remove-empty", action="store_true",
  #                     help="if a pronunciation will be empty after removal, remove the corresponding word from the dictionary")
  parser.add_argument("--removed-out", metavar="PATH", type=get_optional(parse_path),
                      help="write removed words to this file", default=default_removed_out)
  add_n_jobs_argument(parser)
  add_chunksize_argument(parser)
  add_maxtaskperchild_argument(parser)
  return remove_symbols_from_words


def remove_symbols_from_words(dictionaries: OrderedSet[Path], symbols: OrderedSet[Symbol], mode: str, removed_out: Optional[Path], n_jobs: int, maxtasksperchild: Optional[int], chunksize: int) -> bool:
  assert len(dictionaries) > 0
  logger = getLogger(__name__)

  symbols_str = ''.join(symbols)

  for dictionary_path in dictionaries:
    try:
      dictionary_instance = parse_dictionary_from_txt(dictionaries[0], PROG_ENCODING)
    except Exception as ex:
      logger.error(f"Dictionary '{dictionary_path}' couldn't be read.")
      return False

    removed_words, changed_counter = remove_symbols(dictionary_instance, symbols_str, mode,
                                                    n_jobs, maxtasksperchild, chunksize)

    if changed_counter == 0:
      logger.info("Didn't changed anything.")
      return True

    logger.info(f"Changed pronunciations of {changed_counter} word(s).")

    success = save_dict(dictionary_instance, dictionary_path)
    if not success:
      return False

    logger.info(f"Written dictionary to: {dictionary_path.absolute()}")

    if len(removed_words) > 0:
      logger.warning(f"{len(removed_words)} words were removed.")
      if removed_out is not None:
        content = "\n".join(removed_words)
        try:
          removed_out.write_text(content, "UTF-8")
        except Exception as ex:
          logger.error("Removed words output couldn't be created!")
          return False
        logger.info(f"Written removed words to: {removed_out.absolute()}")
    else:
      logger.info("No words were removed.")


def remove_symbols(dictionary: PronunciationDict, symbols: str, mode: str, n_jobs: int, maxtasksperchild: Optional[int], chunksize: int) -> Tuple[OrderedSet[Word], int]:
  process_method = partial(
    process_get_word,
    symbols=symbols,
    mode=mode,
  )

  with Pool(
    processes=n_jobs,
    maxtasksperchild=maxtasksperchild,
  ) as pool:
    entries = OrderedSet(dictionary.keys())
    iterator = pool.imap(process_method, entries, chunksize)
    new_words_to_words = dict(tqdm(iterator, total=len(entries), unit="words"))

  changed_counter = 0
  removed_words = OrderedSet()
  all_words_in_order = OrderedSet(dictionary.keys())
  for word in all_words_in_order:
    new_word = new_words_to_words[word]
    changed_word = new_word is not None
    if changed_word:
      pronunciations = dictionary.pop(word)
      if new_word in dictionary:
        dictionary[new_word].update(pronunciations)
      else:
        if new_word == "":
          removed_words.add(word)
        else:
          dictionary[new_word] = pronunciations
      changed_counter += 1

  return removed_words, changed_counter


def process_get_word(word: Word, symbols: str, mode: Literal["all", "start", "end", "both"]) -> Tuple[Word, Optional[Word]]:
  if mode == "all":
    new_word = "".join(
      symbol
      for symbol in word
      if symbol not in symbols
    )
  elif mode == "start":
    new_word = word.lstrip(symbols)
  elif mode == "end":
    new_word = word.rstrip(symbols)
  elif mode == "both":
    new_word = word.strip(symbols)
  else:
    assert False

  if new_word != word:
    return word, new_word
  return word, None