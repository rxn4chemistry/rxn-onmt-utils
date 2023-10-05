import logging
from pathlib import Path

import click
import torch
from rxn.utilities.files import get_file_size_as_string
from rxn.utilities.logging import setup_console_logger

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def strip_model(model_in: Path, model_out: Path) -> None:
    """
    Strip the optim data of the given OpenNMT model.

    This usually reduces the size of the file by 2/3.

    Args:
        model_in: path of the model to strip.
        model_out: where to save the new model (can be identical to ``model_in``).
    """
    orig_size = get_file_size_as_string(model_in)
    logger.info(f'Stripping model "{model_in}" (size: {orig_size})...')

    loaded_model: dict = torch.load(model_in, map_location="cpu")
    loaded_model["optim"] = None
    torch.save(loaded_model, model_out)

    final_size = get_file_size_as_string(model_out)
    logger.info(
        f'Stripping model "{model_in}" (size: {orig_size})... Done. Stripped model saved to "{model_out}" (size: {final_size}).'
    )


@click.command()
@click.option(
    "--model",
    "-m",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="The model filename (*.pt)",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(writable=True, path_type=Path),
    help="The output filename (*.pt)",
)
def main(model: Path, output: Path) -> None:
    """Remove the optim data of PyTorch models."""
    setup_console_logger()
    strip_model(model_in=model, model_out=output)


if __name__ == "__main__":
    main()
