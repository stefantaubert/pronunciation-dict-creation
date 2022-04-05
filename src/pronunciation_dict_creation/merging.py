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
from pronunciation_dict_creation.common import ConvertToOrderedSetAction, DEFAULT_PUNCTUATION, DefaultParameters, PROG_ENCODING, add_chunksize_argument, add_encoding_argument, add_maxtaskperchild_argument, add_n_jobs_argument, get_dictionary, to_text, update_dictionary
from pronunciation_dict_parser import parse_dictionary_from_txt
from pronunciation_dict_creation.word2pronunciation import get_pronunciation_from_word


def get_merging_parser(parser: ArgumentParser):
  parser.description = "Merge multiple dictionaries to one."
  parser.add_argument("dictionaries", metavar='dictionaries', type=parse_existing_file, nargs="+",
                      help="dictionary files", action=ConvertToOrderedSetAction)
  parser.add_argument("output_dictionary", metavar='output-dictionary', type=parse_path,
                      help="file to the output dictionary")
  parser.add_argument("--duplicate-handling", type=str,
                      choices=["add", "extend", "replace"], help="sets how existing pronunciations should be handled: add = add missing pronunciations; extend = add missing pronunciations and extend existing ones; replace: add missing pronunciations and replace existing ones.", default="add")
  #add_n_jobs_argument(parser)
  #add_chunksize_argument(parser)
  #add_maxtaskperchild_argument(parser)
  return
