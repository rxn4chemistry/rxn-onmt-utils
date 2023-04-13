import click
import torch


@click.command()
@click.option("--model", "-m", required=True, help="The model filename (*.pt)")
@click.option("--output", "-o", required=True, help="The output filename (*.pt)")
def main(model: str, output: str):
    """Remove the optim data of PyTorch models."""
    loaded_model: dict = torch.load(model, map_location="cpu")
    loaded_model["optim"] = None
    torch.save(loaded_model, output)


if __name__ == "__main__":
    main()
