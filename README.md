# dict-from-dict

[![PyPI](https://img.shields.io/pypi/v/dict-from-dict.svg)](https://pypi.python.org/pypi/dict-from-dict)
[![PyPI](https://img.shields.io/pypi/pyversions/dict-from-dict.svg)](https://pypi.python.org/pypi/dict-from-dict)
[![MIT](https://img.shields.io/github/license/stefantaubert/pronunciation-dict-creation.svg)](LICENSE)

CLI to create a pronunciation dictionary from an other pronunciation dictionary with the possibility of ignoring punctuation and splitting on hyphens before lookup.

## Installation

```sh
pip install dict-from-dict --user
```

## Usage

```sh
# Create example vocabulary
cat > /tmp/vocabulary.txt << EOF
Test?
abc,
"def
Test-def.
EOF

# Create example dictionary
cat > /tmp/dictionary.dict << EOF
test  0.7  T E0 S T
test  0.3  T E1 S T
def  0.4  D E0 F
def  0.6  D E1 F
EOF

# Create dictionary from example dictionary and vocabulary
dict-from-dict-cli \
  /tmp/vocabulary.txt \
  /tmp/dictionary.dict --consider-weights \
  /tmp/result.dict \
  --ignore-case --split-on-hyphen \
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
# -------

cat /tmp/oov.txt
# -------
# Output:
# -------
# abc,
# -------
```
