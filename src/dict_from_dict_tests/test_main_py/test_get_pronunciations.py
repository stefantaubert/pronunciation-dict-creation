
from collections import OrderedDict

from ordered_set import OrderedSet
from word_to_pronunciation import Options

from dict_from_dict.core import get_pronunciations


def test_component():
  vocabulary = OrderedSet((
    "Test?",
    "Test-def.",
    "abc,",
    "\"def",
  ))
  dictionary = OrderedDict((
    ("test", OrderedDict((
      (("T", "E0", "S", "T"), 0.7),
      (("T", "E1", "S", "T"), 0.3),
    ))),
    ("def", OrderedDict((
      (("D", "E0", "F"), 1.0),
    ))),
  ))
  options = Options("?,\".", True, True, True, 1.0)

  result_dict, result_oov = get_pronunciations(
    vocabulary, dictionary, options, True, 1, None, 4, silent=True)

  assert len(result_dict) == 3
  assert len(result_oov) == 1
