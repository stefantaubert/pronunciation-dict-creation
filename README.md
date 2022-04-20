# dict-from-dict

[![PyPI](https://img.shields.io/pypi/v/dict-from-dict.svg)](https://pypi.python.org/pypi/dict-from-dict)
[![PyPI](https://img.shields.io/pypi/pyversions/dict-from-dict.svg)](https://pypi.python.org/pypi/dict-from-dict)
[![MIT](https://img.shields.io/github/license/stefantaubert/pronunciation-dict-creation.svg)](LICENSE)

CLI to create a pronunciation dictionary from an other pronunciation dictionary with the possibility of ignoring punctuation and splitting on hyphens before lookup.

## Features

- ignore casing of words while lookup
- trimming symbols at start and end of word before lookup
- separate word on hyphen before lookup
  - if the dictionary contains words with hyphens they will be considered first (see example below)
- words with multiple pronunciations are supported
  - weights will be multiplied for hyphenated words (see example below)
- outputting OOV words
- multiprocessing

## Installation

```sh
pip install dict-from-dict --user
```

## Usage

```sh
dict-from-dict-cli
```

### Example

```sh
# Create example vocabulary
cat > /tmp/vocabulary.txt << EOF
Test?
abc,
"def
Test-def.
"xyz?
"uv-w?
EOF

# Create example dictionary
cat > /tmp/dictionary.dict << EOF
test  0.7  T E0 S T
test  0.3  T E1 S T
def  0.4  D E0 F
def  0.6  D E1 F
xyz  2.0  ?
"xyz?  1.0  " X Y Z ?
uv  2.0  ?
w  2.0  ?
uv-w  1.0  U V - W
EOF

# Create dictionary from vocabulary and example dictionary
dict-from-dict-cli \
  /tmp/vocabulary.txt \
  /tmp/dictionary.dict --consider-weights \
  /tmp/result.dict \
  --ignore-case --split-on-hyphen \
  --n-jobs 4 \
  --oov-out /tmp/oov.txt

cat /tmp/result.dict
# -------
# Output:
# -------
# Test?  0.7  T E0 S T ?
# Test?  0.3  T E1 S T ?
# "def  0.4  " D E0 F
# "def  0.6  " D E1 F
# Test-def.  0.27999999999999997  T E0 S T - D E0 F .
# Test-def.  0.42  T E0 S T - D E1 F .
# Test-def.  0.12  T E1 S T - D E0 F .
# Test-def.  0.18  T E1 S T - D E1 F .
# "xyz?  1.0  " X Y Z ?
# "uv-w?  1.0  " U V - W ?
# -------

cat /tmp/oov.txt
# -------
# Output:
# -------
# abc,
# -------
```
