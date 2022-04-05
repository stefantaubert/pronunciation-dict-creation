from argparse import ArgumentParser
from logging import getLogger
from pathlib import Path
from typing import Literal
from pronunciation_dict_parser import PronunciationDict
from ordered_set import OrderedSet
from pronunciation_dict_creation.argparse_helper import parse_existing_file, parse_path
from pronunciation_dict_creation.common import ConvertToOrderedSetAction, PROG_ENCODING, save_dict
from pronunciation_dict_parser import parse_dictionary_from_txt


def get_merging_parser(parser: ArgumentParser):
  parser.description = "Merge multiple dictionaries into one."
  parser.add_argument("dictionaries", metavar='dictionaries', type=parse_existing_file, nargs="+",
                      help="dictionary files", action=ConvertToOrderedSetAction)
  parser.add_argument("output_dictionary", metavar='output-dictionary', type=parse_path,
                      help="file to the output dictionary")
  parser.add_argument("--duplicate-handling", type=str,
                      choices=["add", "extend", "replace"], help="sets how existing pronunciations should be handled: add = add missing pronunciations; extend = add missing pronunciations and extend existing ones; replace: add missing pronunciations and replace existing ones.", default="add")
  return merge_dictionary_files


def merge_dictionary_files(dictionaries: OrderedSet[Path], output_dictionary: Path, duplicate_handling: Literal["add", "extend", "replace"]) -> bool:
  assert len(dictionaries) > 0
  logger = getLogger(__name__)
  if len(dictionaries) == 1:
    logger.error("Please supply more than one dictionary!")
    return False

  resulting_dictionary = None

  for dictionary in dictionaries:
    try:
      dictionary_instance = parse_dictionary_from_txt(dictionaries[0], PROG_ENCODING)
    except Exception as ex:
      logger.error(f"Dictionary '{dictionary}' couldn't be read.")
      return False
    if resulting_dictionary is None:
      resulting_dictionary = dictionary_instance
      continue

    if duplicate_handling == "add":
      dictionary_add_new(resulting_dictionary, dictionary_instance)
    elif duplicate_handling == "replace":
      dictionary_replace(resulting_dictionary, dictionary_instance)
    elif duplicate_handling == "extend":
      dictionary_extend(resulting_dictionary, dictionary_instance)
    else:
      assert False

  success = save_dict(resulting_dictionary, output_dictionary)
  if not success:
    return False

  logger.info(f"Written dictionary to: {output_dictionary.absolute()}")


def dictionary_replace(dictionary1: PronunciationDict, dictionary2: PronunciationDict) -> None:
  dictionary1.update(dictionary2)


def dictionary_add_new(dictionary1: PronunciationDict, dictionary2: PronunciationDict) -> None:
  new_keys = OrderedSet(dictionary2.keys()).difference(dictionary1.keys())
  for key in new_keys:
    assert key not in dictionary1
    dictionary1[key] = dictionary2[key]


def dictionary_extend(dictionary1: PronunciationDict, dictionary2: PronunciationDict) -> None:
  keys = OrderedSet(dictionary2.keys())
  same_keys = keys.intersection(dictionary1.keys())
  new_keys = keys.difference(dictionary1.keys())

  for key in same_keys:
    assert key in dictionary1
    dictionary1[key].update(dictionary2[key])

  for key in new_keys:
    assert key not in dictionary1
    dictionary1[key] = dictionary2[key]
