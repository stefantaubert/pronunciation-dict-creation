from tempfile import gettempdir
from argparse import ArgumentParser
import argparse
from collections import OrderedDict
from logging import getLogger
from pathlib import Path
from tqdm import tqdm
from dataclasses import dataclass
from email.policy import default
from functools import partial
from multiprocessing.pool import Pool
from typing import Literal, Optional, Set, Tuple
from pronunciation_dict_parser import Pronunciation, PronunciationDict, Symbol, Word, Pronunciations
from ordered_set import OrderedSet
from pronunciation_dict_creation.argparse_helper import get_optional, parse_existing_file, parse_non_empty_or_whitespace, parse_path
from pronunciation_dict_creation.common import ConvertToOrderedSetAction, DEFAULT_PUNCTUATION, DefaultParameters, PROG_ENCODING, add_chunksize_argument, add_encoding_argument, add_maxtaskperchild_argument, add_n_jobs_argument, to_text, update_dictionary
from pronunciation_dict_parser import parse_dictionary_from_txt
from pronunciation_dict_creation.word2pronunciation import get_pronunciation_from_word


def get_app_try_add_vocabulary_from_pronunciations_parser(parser: ArgumentParser):
  default_unresolved_out = Path(gettempdir()) / "unresolved.txt"
  parser.description = "Transcribe vocabulary with a given pronunciation dictionary and add it to an existing pronunciation dictionary or create one."
  parser.add_argument("vocabulary", metavar='vocabulary', type=parse_existing_file,
                      help="file containing the vocabulary (words separated by line)")
  parser.add_argument("dictionary", metavar='dictionary', type=parse_path,
                      help="file containing the output dictionary")
  parser.add_argument("reference_dictionary", metavar='reference-dictionary', type=parse_existing_file,
                      help="file containing the reference dictionary")
  parser.add_argument("--ignore-case", action="store_true",
                      help="ignore case while looking up in reference-dictionary")
  parser.add_argument("--punctuation", type=parse_non_empty_or_whitespace, metavar='SYMBOL', nargs='*',
                      help="trim these punctuation symbols from the start and end of a word before looking it up in the reference pronunciation dictionary", action=ConvertToOrderedSetAction, default=DEFAULT_PUNCTUATION)
  parser.add_argument("--duplicate-handling", type=str,
                      choices=["ignore", "replace", "add"], help="sets how existing pronunciations should be handled", default="ignore")
  parser.add_argument("--consider-annotations", action="store_true",
                      help="consider /.../-styled annotations")
  parser.add_argument("--split-on-hyphen", action="store_true",
                      help="split words on hyphen symbol before lookup")
  parser.add_argument("--unresolved-out", metavar="PATH", type=get_optional(parse_path),
                      help="write unresolved vocabulary to this file", default=default_unresolved_out)
  add_encoding_argument(parser, "--encoding", "encoding of vocabulary")
  add_n_jobs_argument(parser)
  add_chunksize_argument(parser)
  add_maxtaskperchild_argument(parser)
  return app_try_add_vocabulary_from_pronunciations


def app_try_add_vocabulary_from_pronunciations(vocabulary: Path, encoding: str, dictionary: Path, reference_dictionary: Path, ignore_case: bool, punctuation: OrderedSet[Symbol], consider_annotations: bool, split_on_hyphen: bool, duplicate_handling: str, unresolved_out: Optional[Path], n_jobs, maxtasksperchild: Optional[int], chunksize: int) -> bool:
  assert vocabulary.is_file()
  assert reference_dictionary.is_file()
  logger = getLogger(__name__)

  if dictionary.exists():
    try:
      dictionary_instance = parse_dictionary_from_txt(dictionary, PROG_ENCODING)
    except Exception as ex:
      logger.error("Dictionary couldn't be read.")
      return False
  else:
    dictionary_instance = OrderedDict()

  try:
    vocabulary_content = vocabulary.read_text(encoding)
  except Exception as ex:
    logger.error("Vocabulary couldn't be read.")
    return False

  try:
    reference_dictionary_instance = parse_dictionary_from_txt(
      reference_dictionary, PROG_ENCODING)
  except Exception as ex:
    logger.error("Reference dictionary couldn't be read.")
    return False

  vocabulary_words = OrderedSet(vocabulary_content.splitlines())
  params = DefaultParameters(dictionary_instance, vocabulary_words, consider_annotations, "/",
                             duplicate_handling, split_on_hyphen, punctuation, n_jobs, maxtasksperchild, chunksize)

  unresolved_words = try_add_vocabulary_from_pronunciations(
    params, reference_dictionary_instance, ignore_case)

  dict_content = to_text(dictionary_instance, "\t", " ", True, False, "")
  try:
    dictionary.write_text(dict_content, PROG_ENCODING)
  except Exception as ex:
    logger.error("Dictionary couldn't be written.")
    return False
  logger.info(f"Written dictionary to: {dictionary.absolute()}")

  if len(unresolved_words) > 0:
    logger.warning("Not all words were contained in the reference dictionary")
    if unresolved_out is not None:
      unresolved_out_content = "\n".join(unresolved_words)
      try:
        unresolved_out.write_text(unresolved_out_content, "UTF-8")
      except Exception as ex:
        logger.error("Unresolved output couldn't be created!")
        return False
      logger.info(f"Written unresolved to: {unresolved_out.absolute()}")
  else:
    logger.info("Complete vocabulary is contained in output!")

  return True


process_unique_words: OrderedSet[Word] = None
process_lookup_dict: PronunciationDict = None


def __init_pool_prepare_cache_mp(words: OrderedSet[Word], lookup_dict: PronunciationDict) -> None:
  global process_unique_words
  process_unique_words = words
  lookup_dict = lookup_dict


def lookup_in_dict_process(word_i: int, ignore_case: bool) -> Tuple[int, Pronunciations]:
  global process_unique_words
  global process_lookup_dict
  assert word_i in process_unique_words
  word = process_unique_words[word_i]
  if ignore_case:
    word = word.lower()
  result = process_lookup_dict.get(word, None)
  return word_i, result


def dict_words_to_lower(lookup_dict: PronunciationDict) -> PronunciationDict:
  result = PronunciationDict()
  for word, pronunciations in lookup_dict.items():
    word = word.lower()
    if word in result:
      result[word].update(pronunciations)
    else:
      result[word] = pronunciations
  return result


def try_add_vocabulary_from_pronunciations(default_params: DefaultParameters, lookup_dict: PronunciationDict, lookup_ignore_case: bool) -> OrderedSet[Word]:
  internal_lookup = partial(
    lookup_in_dict_process,
    ignore_case=lookup_ignore_case,
  )

  lookup_method = partial(
    get_pronunciation_from_word,
    trim_symbols=default_params.trim,
    split_on_hyphen=default_params.split_on_hyphen,
    get_pronunciation=internal_lookup,
    considder_annotation=default_params.consider_annotations,
    annotation_split_symbol=default_params.annotation_split_symbol,
  )

  if default_params.handle_duplicates == "ignore":
    words_to_lookup = default_params.vocabulary.difference(default_params.target_dictionary.keys())
  else:
    words_to_lookup = default_params.vocabulary

  if lookup_ignore_case:
    lookup_dict = dict_words_to_lower(lookup_dict)

  with Pool(
    processes=default_params.n_jobs,
    initializer=__init_pool_prepare_cache_mp,
    initargs=(words_to_lookup, lookup_dict),
    maxtasksperchild=default_params.maxtasksperchild,
  ) as pool:
    iterator = pool.imap_unordered(lookup_method, range(
      len(words_to_lookup)), default_params.chunksize)
    pronunciations_to_i = list(tqdm(iterator, total=len(words_to_lookup), unit="words"))

  unresolved_words = update_dictionary(default_params.target_dictionary, pronunciations_to_i,
                                       words_to_lookup, default_params.handle_duplicates)
  return unresolved_words
