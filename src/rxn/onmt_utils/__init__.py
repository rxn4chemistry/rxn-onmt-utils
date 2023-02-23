# LICENSED INTERNAL CODE. PROPERTY OF IBM.
# IBM Research Zurich Licensed Internal Code
# (C) Copyright IBM Corp. 2021
# ALL RIGHTS RESERVED

__version__ = "0.8.3.dev3"  # managed by bump2version

from rxn.onmt_utils.translate import translate
from rxn.onmt_utils.translator import Translator

__all__ = [
    "translate",
    "Translator",
]
