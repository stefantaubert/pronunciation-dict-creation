from collections import OrderedDict

from ordered_set import OrderedSet

from dict_from_dict.core import create_dict_from_dict


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
      (("D", "E0", "F"), 2.0),
    ))),
  ))

  result_dict, result_oov = create_dict_from_dict(
    vocabulary, dictionary, set("?,\"."), True, True, 1, None, 4, silent=True)

  assert result_dict == OrderedDict([('Test?', OrderedDict([(('T', 'E0', 'S', 'T', '?'), 0.7), (('T', 'E1', 'S', 'T', '?'), 0.3)])), ('Test-def.', OrderedDict(
    [(('T', 'E0', 'S', 'T', '-', 'D', 'E0', 'F', '.'), 1.4), (('T', 'E1', 'S', 'T', '-', 'D', 'E0', 'F', '.'), 0.6)])), ('"def', OrderedDict([(('"', 'D', 'E0', 'F'), 2.0)]))])
  assert result_oov == OrderedSet(['abc,'])
