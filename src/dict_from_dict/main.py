from argparse import ArgumentParser, Namespace
from collections import OrderedDict
from functools import partial
from logging import getLogger
from multiprocessing.pool import Pool
from pathlib import Path
from tempfile import gettempdir
from typing import Dict, Optional, Tuple

from ordered_set import OrderedSet
from pronunciation_dictionary import (DeserializationOptions, MultiprocessingOptions,
                                      PronunciationDict, Pronunciations, SerializationOptions, Word,
                                      change_word_casing, load_dict, save_dict)
from tqdm import tqdm
from word_to_pronunciation import Options, get_pronunciations_from_word

from dict_from_dict.argparse_helper import (DEFAULT_PUNCTUATION, ConvertToOrderedSetAction,
                                            add_chunksize_argument, add_encoding_argument,
                                            add_io_group, add_maxtaskperchild_argument,
                                            add_n_jobs_argument, get_optional, parse_existing_file,
                                            parse_non_empty_or_whitespace, parse_path)


def get_app_try_add_vocabulary_from_pronunciations_parser(parser: ArgumentParser):
  default_oov_out = Path(gettempdir()) / "oov.txt"
  parser.description = "Transcribe vocabulary with a given pronunciation dictionary."
  # TODO support multiple files
  parser.add_argument("vocabulary", metavar='vocabulary', type=parse_existing_file,
                      help="file containing the vocabulary (words separated by line)")
  parser.add_argument("reference_dictionary", metavar='reference-dictionary', type=parse_existing_file,
                      help="file containing the reference pronunciation dictionary")
  parser.add_argument("dictionary", metavar='dictionary', type=parse_path,
                      help="path to output created dictionary")
  parser.add_argument("--ignore-case", action="store_true",
                      help="ignore case while looking up in reference-dictionary")
  parser.add_argument("--trim", type=parse_non_empty_or_whitespace, metavar='SYMBOL', nargs='*',
                      help="trim these symbols from the start and end of a word before looking it up in the reference pronunciation dictionary", action=ConvertToOrderedSetAction, default=DEFAULT_PUNCTUATION)
  parser.add_argument("--split-on-hyphen", action="store_true",
                      help="split words on hyphen symbol before lookup")
  parser.add_argument("--oov-out", metavar="PATH", type=get_optional(parse_path),
                      help="write out-of-vocabulary (OOV) words (i.e., words that did not exist in the reference dictionary) to this file (encoding will be the same as the one from the vocabulary file)", default=default_oov_out)
  add_encoding_argument(parser, "--vocabulary-encoding", "encoding of vocabulary")
  add_io_group(parser)
  mp_group = parser.add_argument_group("multiprocessing arguments")
  add_n_jobs_argument(mp_group)
  add_chunksize_argument(mp_group)
  add_maxtaskperchild_argument(mp_group)
  return get_pronunciations_files


def get_pronunciations_files(ns: Namespace) -> bool:
  assert ns.vocabulary.is_file()
  assert ns.reference_dictionary.is_file()
  logger = getLogger(__name__)

  try:
    vocabulary_content = ns.vocabulary.read_text(ns.vocabulary_encoding)
  except Exception as ex:
    logger.error("Vocabulary couldn't be read.")
    return False

  lp_options = DeserializationOptions(
      ns.consider_comments, ns.consider_numbers, ns.consider_pronunciation_comments, ns.consider_weights)
  mp_options = MultiprocessingOptions(ns.n_jobs, ns.maxtasksperchild, ns.chunksize)

  s_options = SerializationOptions(ns.parts_sep, ns.consider_numbers, ns.consider_weights)

  try:
    reference_dictionary_instance = load_dict(
      ns.reference_dictionary, ns.encoding, lp_options, mp_options)
  except Exception as ex:
    logger.error("Reference dictionary couldn't be read.")
    return False

  vocabulary_words = OrderedSet(vocabulary_content.splitlines())
  trim_symbols = ''.join(ns.trim)
  options = Options(trim_symbols, ns.split_on_hyphen, True, True, 1.0)

  dictionary_instance, unresolved_words = get_pronunciations(vocabulary_words,
                                                             reference_dictionary_instance, options, ns.ignore_case, ns.n_jobs, ns.maxtasksperchild, ns.chunksize)

  try:
    save_dict(dictionary_instance, ns.dictionary, ns.encoding, s_options)
  except Exception as ex:
    logger.error("Dictionary couldn't be written.")
    return False

  logger.info(f"Written dictionary to: {ns.dictionary.absolute()}")

  if len(unresolved_words) > 0:
    logger.warning("Not all words were contained in the reference dictionary")
    if ns.oov_out is not None:
      unresolved_out_content = "\n".join(unresolved_words)
      ns.oov_out.parent.mkdir(parents=True, exist_ok=True)
      try:
        ns.oov_out.write_text(unresolved_out_content, "UTF-8")
      except Exception as ex:
        logger.error("Unresolved output file couldn't be created!")
        return False
      logger.info(f"Written unresolved vocabulary to: {ns.oov_out.absolute()}")
  else:
    logger.info("Complete vocabulary is contained in output!")

  return True


def get_pronunciations(vocabulary: OrderedSet[Word], lookup_dict: PronunciationDict, options: Options, lookup_ignore_case: bool, n_jobs: int, maxtasksperchild: Optional[int], chunksize: int) -> Tuple[PronunciationDict, OrderedSet[Word]]:
  lookup_method = partial(
    process_get_pronunciation,
    options=options,
    ignore_case=lookup_ignore_case,
  )

  if lookup_ignore_case:
    mp_options = MultiprocessingOptions(n_jobs, maxtasksperchild, chunksize)
    change_word_casing(lookup_dict, "lower", 0.5, mp_options)

  with Pool(
    processes=n_jobs,
    initializer=__init_pool_prepare_cache_mp,
    initargs=(vocabulary, lookup_dict),
    maxtasksperchild=maxtasksperchild,
  ) as pool:
    entries = range(len(vocabulary))
    iterator = pool.imap(lookup_method, entries, chunksize)
    pronunciations_to_i = dict(tqdm(iterator, total=len(entries), unit="words"))

  return get_dictionary(pronunciations_to_i, vocabulary)


def get_dictionary(pronunciations_to_i: Dict[int, Pronunciations], vocabulary: OrderedSet[Word]) -> Tuple[PronunciationDict, OrderedSet[Word]]:
  resulting_dict = OrderedDict()
  unresolved_words = OrderedSet()

  for i, word in enumerate(vocabulary):
    pronunciations = pronunciations_to_i[i]

    if len(pronunciations) == 0:
      unresolved_words.add(word)
      continue
    assert word not in resulting_dict
    resulting_dict[word] = pronunciations

  return resulting_dict, unresolved_words


process_unique_words: OrderedSet[Word] = None
process_lookup_dict: PronunciationDict = None


def __init_pool_prepare_cache_mp(words: OrderedSet[Word], lookup_dict: PronunciationDict) -> None:
  global process_unique_words
  global process_lookup_dict
  process_unique_words = words
  process_lookup_dict = lookup_dict


def process_get_pronunciation(word_i: int, ignore_case: bool, options: Options) -> Tuple[int, Pronunciations]:
  global process_unique_words
  global process_lookup_dict
  assert 0 <= word_i < len(process_unique_words)
  word = process_unique_words[word_i]

  # TODO support all entries; also create all combinations with hyphen then
  lookup_method = partial(
    lookup_in_dict,
    dictionary=process_lookup_dict,
    ignore_case=ignore_case,
  )

  pronunciations = get_pronunciations_from_word(word, lookup_method, options)

  return word_i, pronunciations


def lookup_in_dict(word: Word, dictionary: PronunciationDict, ignore_case: bool) -> Pronunciations:
  if ignore_case:
    word = word.lower()
  if word in dictionary:
    result = dictionary[word]
  else:
    result = OrderedDict()
  return result
