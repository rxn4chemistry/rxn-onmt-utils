#!/usr/bin/env python
# LICENSED INTERNAL CODE. PROPERTY OF IBM.
# IBM Research Zurich Licensed Internal Code
# (C) Copyright IBM Corp. 2020
# ALL RIGHTS RESERVED


def translate_standardize(
    input_file_path: str, output_file_path: str, fragment_bond: str = "."
) -> None:
    """Standardize for translation.

    Args:
        input_file_path (str):  The input file path (one SMILES per line).
        output_file_path (str): The output file path.
        fragment_bond (str): The fragment bond token used in the files to be standardized
    """

    # # Create a instance of the Patterns.
    # # for now jsonpath and fragment_bond (the one present in the jsonfile) fixed
    # json_file_path = str(standardization_files_directory() / 'pistachio-200302.json')
    # pt = rrp.Patterns(json_file_path, fragment_bond='~')
    #
    # # Create an instance of the Standardizer
    # std = rrp.Standardizer.read_csv(
    #     input_file_path, pt, reaction_column_name='rxn', fragment_bond=fragment_bond
    # )
    # # Perform standardization
    # std.standardize()
    #
    # # Exporting standardized samples
    # std.df.to_csv(output_file_path)

    raise RuntimeError("Not adapted yet to the new syntax")