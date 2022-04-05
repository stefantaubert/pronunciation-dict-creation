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
from pronunciation_dict_creation.word2pronunciation import get_pronunciation_from_word


def get_pronunciations_remove_symbols_parser(parser: ArgumentParser):
  parser.description = "Remove symbols from pronunciations."
  parser.add_argument("dictionaries", metavar='dictionaries', type=parse_existing_file, nargs="+",
                      help="dictionary files", action=ConvertToOrderedSetAction)
  parser.add_argument("--symbols", type=str, metavar='SYMBOL', nargs='+',
                      help="remove these symbols from the pronunciations", action=ConvertToOrderedSetAction, default=DEFAULT_PUNCTUATION)
  # parser.add_argument("--remove-empty", action="store_true",
  #                     help="if a pronunciation will be empty after removal, remove the corresponding word from the dictionary")
  add_n_jobs_argument(parser)
  add_chunksize_argument(parser)
  add_maxtaskperchild_argument(parser)
  return remove_symbols_from_pronunciations


def remove_symbols_from_pronunciations(dictionaries: OrderedSet[Path], symbols: OrderedSet[Symbol], n_jobs: int, maxtasksperchild: Optional[int], chunksize: int) -> bool:
  assert len(dictionaries) > 0
  logger = getLogger(__name__)

  for dictionary_path in dictionaries:
    try:
      dictionary_instance = parse_dictionary_from_txt(dictionaries[0], PROG_ENCODING)
    except Exception as ex:
      logger.error(f"Dictionary '{dictionary_path}' couldn't be read.")
      return False

    changed_counter = remove_symbols(dictionary_instance, symbols,
                                     n_jobs, maxtasksperchild, chunksize)

    if changed_counter == 0:
      logger.info("Didn't changed anything.")
      return True

    logger.info(f"Changed pronunciations of {changed_counter} word(s).")

    success = save_dict(dictionary_instance, dictionary_path)
    if not success:
      return False

    logger.info(f"Written dictionary to: {dictionary_path.absolute()}")


def remove_symbols(dictionary: PronunciationDict, symbols: OrderedSet[Symbol], n_jobs: int, maxtasksperchild: Optional[int], chunksize: int) -> int:
  process_method = partial(
    process_get_pronunciation,
    symbols=symbols,
  )

  with Pool(
    processes=n_jobs,
    initializer=__init_pool_prepare_cache_mp,
    initargs=(dictionary,),
    maxtasksperchild=maxtasksperchild,
  ) as pool:
    entries = OrderedSet(dictionary.keys())
    iterator = pool.imap(process_method, entries, chunksize)
    pronunciations_to_i = list(tqdm(iterator, total=len(entries), unit="words"))

  changed_counter = 0
  for word, pronunciations in pronunciations_to_i:
    changed_anything = pronunciations is not None
    if changed_anything:
      dictionary[word] = pronunciations
      changed_counter += 1

  return changed_counter


process_lookup_dict: PronunciationDict = None


def __init_pool_prepare_cache_mp(lookup_dict: PronunciationDict) -> None:
  global process_lookup_dict
  process_lookup_dict = lookup_dict


def process_get_pronunciation(word: Word, symbols: Set[Symbol]) -> Tuple[Word, Optional[Pronunciations]]:
  global process_lookup_dict
  assert word in process_lookup_dict
  pronunciations = process_lookup_dict[word]
  result = OrderedSet()
  changed_anything = False
  for pronunciation in pronunciations:
    new_pronunciation = tuple(
      symbol
      for symbol in pronunciation
      if symbol not in symbols
    )
    result.add(new_pronunciation)
    if new_pronunciation != pronunciation:
      changed_anything = True

  if changed_anything:
    return word, result
  return word, None
