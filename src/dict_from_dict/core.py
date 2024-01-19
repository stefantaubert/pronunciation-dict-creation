from collections import OrderedDict
from functools import partial
from multiprocessing.pool import Pool
from typing import Dict, Optional, Set, Tuple

from ordered_set import OrderedSet
from pronunciation_dictionary import MultiprocessingOptions, PronunciationDict, Pronunciations, Word
from pronunciation_dictionary_utils import change_word_casing
from tqdm import tqdm
from word_to_pronunciation import Options, get_pronunciations_from_word


def create_dict_from_dict(vocabulary_words: OrderedSet[Word], reference_dict: PronunciationDict, trim: Set, split_on_hyphen: bool, ignore_case: bool, n_jobs: int, maxtasksperchild: Optional[int], chunksize: int, silent: bool = False) -> Tuple[PronunciationDict, OrderedSet[Word]]:
  trim_symbols = ''.join(trim)
  options = Options(trim_symbols, split_on_hyphen, True, True, 1.0)

  dictionary_instance, unresolved_words = get_pronunciations(
    vocabulary_words, reference_dict, options, ignore_case, n_jobs, maxtasksperchild, chunksize, silent)
  return dictionary_instance, unresolved_words


def get_pronunciations(vocabulary: OrderedSet[Word], lookup_dict: PronunciationDict, options: Options, lookup_ignore_case: bool, n_jobs: int, maxtasksperchild: Optional[int], chunksize: int, silent: bool) -> Tuple[PronunciationDict, OrderedSet[Word]]:
  lookup_method = partial(
    process_get_pronunciation,
    options=options,
    ignore_case=lookup_ignore_case,
  )

  if lookup_ignore_case:
    mp_options = MultiprocessingOptions(n_jobs, maxtasksperchild, chunksize)
    change_word_casing(lookup_dict, "lower", mp_options, silent=silent)

  with Pool(
    processes=n_jobs,
    initializer=__init_pool_prepare_cache_mp,
    initargs=(vocabulary, lookup_dict),
    maxtasksperchild=maxtasksperchild,
  ) as pool:
    entries = range(len(vocabulary))
    iterator = pool.imap(lookup_method, entries, chunksize)
    pronunciations_to_i = dict(tqdm(iterator, total=len(entries), unit="words", disable=silent))

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
