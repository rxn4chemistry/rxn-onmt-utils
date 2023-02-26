# RXN package for OpenNMT-related utilities

[![Actions tests](https://github.com/rxn4chemistry/rxn-onmt-utils/actions/workflows/tests.yaml/badge.svg)](https://github.com/rxn4chemistry/rxn-onmt-utils/actions)

This repository contains OpenNMT-related utilities used in the RXN universe.
For general utilities not related to OpenNMT, see our other repository [`rxn-utilities`](https://github.com/rxn4chemistry/rxn-utilities).

The documentation can be found [here](https://rxn4chemistry.github.io/rxn-onmt-utils/).

## System Requirements

This package is supported on all operating systems. 
It has been tested on the following systems:
+ macOS: Big Sur (11.1)
+ Linux: Ubuntu 18.04.4

A Python version of 3.6, 3.7, or 3.8 is recommended.
Python versions 3.9 and above are not expected to work due to compatibility with the selected version of OpenNMT.

## Installation guide

The package can be installed from Pypi:
```bash
pip install rxn-onmt-utils
```

For local development, the package can be installed with:
```bash
pip install -e ".[dev]"
```

## Package highlights

### Translate with OpenNMT from Python code

By importing the following,
```python
from rxn.onmt_utils import Translator, translate
```
you can do OpenNMT translations directly in Python. 
The `translate` function acts on input/output files, while the `Translator` class gives you flexibility for getting translation results on strings directly.


### Stripping models

The script `rxn-strip-opennmt-model` installed the package allows you to strip ~2/3 of the size of model checkpoints by removing the state of the optimizer.
You can do this safely if you don't need to continue training on these checkpoints.


### Extending the model vocabulary

If you finetune a model on a dataset with additional tokens compared to the base model, you will need to extend the model weights.
The script `rxn-extend-model-with-vocab` does that for you.
