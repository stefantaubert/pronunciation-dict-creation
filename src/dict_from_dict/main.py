from argparse import ArgumentParser, Namespace
from logging import getLogger
from pathlib import Path
from tempfile import gettempdir

from ordered_set import OrderedSet
from pronunciation_dictionary import (DeserializationOptions, MultiprocessingOptions,
                                      SerializationOptions, load_dict, save_dict)

from dict_from_dict.argparse_helper import (DEFAULT_PUNCTUATION, ConvertToOrderedSetAction,
                                            add_chunksize_argument, add_encoding_argument,
                                            add_io_group, add_maxtaskperchild_argument,
                                            add_n_jobs_argument, get_optional, parse_existing_file,
                                            parse_non_empty_or_whitespace, parse_path)
from dict_from_dict.core import create_dict_from_dict


def get_app_try_add_vocabulary_from_pronunciations_parser(parser: ArgumentParser):
  default_oov_out = Path(gettempdir()) / "oov.txt"
  parser.description = "Transcribe vocabulary with a given pronunciation dictionary."
  # TODO support multiple files
  parser.add_argument("vocabulary", metavar='VOCABULARY', type=parse_existing_file,
                      help="file containing the vocabulary (words separated by line)")
  parser.add_argument("reference_dictionary", metavar='REFERENCE-DICTIONARY', type=parse_existing_file,
                      help="file containing the reference pronunciation dictionary")
  parser.add_argument("dictionary", metavar='DICTIONARY', type=parse_path,
                      help="path to output created dictionary")
  parser.add_argument("--ignore-case", action="store_true",
                      help="ignore case while looking up in reference-dictionary")
  parser.add_argument("--trim", type=parse_non_empty_or_whitespace, metavar='SYMBOL', nargs='*',
                      help="trim these symbols from the start and end of a word before looking it up in the reference pronunciation dictionary", action=ConvertToOrderedSetAction, default=DEFAULT_PUNCTUATION)
  parser.add_argument("--split-on-hyphen", action="store_true",
                      help="split words on hyphen symbol before lookup")
  parser.add_argument("--oov-out", metavar="OOV-PATH", type=get_optional(parse_path),
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
  dictionary_instance, unresolved_words = create_dict_from_dict(
    vocabulary_words, reference_dictionary_instance, ns.trim, ns.split_on_hyphen, ns.ignore_case, ns.n_jobs, ns.maxtasksperchild, ns.chunksize)

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
