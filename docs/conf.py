# Configuration file for the Sphinx documentation builder.

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "sqlatypemodel"
copyright = "2026, GrehBan"
author = "GrehBan"
version = "0.8.4"
release = "0.8.4"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_copybutton",
    "sphinx_substitution_extensions",
]

html_theme = "furo"
html_static_path = ["_static"]

# Suppress non-critical warnings
suppress_warnings = [
    "ref.python",  # Duplicate cross-reference warnings
    "ref.ref",  # Undefined label warnings (phantom warnings from autodoc)
]

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# Copybutton settings
copybutton_prompt_text = r">>> |\.\.\. "
copybutton_prompt_is_regexp = True
