from collections import OrderedDict
from dataclasses import dataclass
from logging import getLogger

from pronunciation_dict_parser.core.types import PronunciationDict
from argparse import ArgumentParser
from logging import getLogger
from pathlib import Path
from tempfile import gettempdir


from pathlib import Path

from pronunciation_dict_parser.core.parser import parse_url
from pronunciation_dict_creation.argparse_helper import parse_path

from pronunciation_dict_creation.common import PROG_ENCODING, to_text


@dataclass()
class PublicDict():
  url: str
  encoding: str
  description: str


public_dicts = OrderedDict((
  ("cmu", PublicDict(
    "http://svn.code.sf.net/p/cmusphinx/code/trunk/cmudict/cmudict-0.7b",
    "ISO-8859-1", "CMU (ARPA)")),
  ("librispeech", PublicDict(
    "https://www.openslr.org/resources/11/librispeech-lexicon.txt",
    "UTF-8", "LibriSpeech (ARPA)")),
  ("mfa", PublicDict(
    "https://raw.githubusercontent.com/MontrealCorpusTools/mfa-models/main/dictionary/english.dict", "UTF-8", "MFA (ARPA)")),
  ("mfa-en-uk", PublicDict(
    "https://raw.githubusercontent.com/MontrealCorpusTools/mfa-models/main/dictionary/english_uk_ipa.dict", "UTF-8", "MFA en-UK (IPA)")),
  ("mfa-en-us", PublicDict(
    "https://raw.githubusercontent.com/MontrealCorpusTools/mfa-models/main/dictionary/english_us_ipa.dict", "UTF-8", "MFA en-US (IPA)")),
  ("prosodylab", PublicDict(
    "https://raw.githubusercontent.com/prosodylab/Prosodylab-Aligner/master/eng.dict",
    "UTF-8", "Prosodylab (ARPA)")),
))


def get_downloading_parser(parser: ArgumentParser):
  parser.description = "Download a public dictionary."
  default_path = Path(gettempdir()) / "pronunciations.dict"
  parser.add_argument("dictionary", metavar='NAME', choices=list(public_dicts.keys()),
                      type=str, help="pronunciation dictionary")
  parser.add_argument("--path", type=parse_path, metavar='PATH',
                      help="file where to output pronunciation dictionary", default=default_path)
  return app_download


def app_download(dictionary: str, path: Path) -> bool:
  logger = getLogger(__name__)

  pronunciation_dict = download_dict(dictionary)
  output_content = to_text(pronunciation_dict)
  try:
    path.write_text(output_content, PROG_ENCODING)
  except Exception as ex:
    logger.error("Couldn't write to file.")
    return False

  logger.info(f"Written dictionary to: {path.absolute()}")
  return True


def download_dict(dictionary: str) -> PronunciationDict:
  assert dictionary in public_dicts

  logger = getLogger(__name__)
  dictionary_info = public_dicts[dictionary]

  logger.info(f"Downloading {dictionary_info.description}...")

  pronunciation_dict = parse_url(dictionary_info.url, dictionary_info.encoding)
  return pronunciation_dict
