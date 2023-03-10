import logging
from typing import List

import torch
import torch.nn as nn
from onmt.model_builder import build_model  # type: ignore
from onmt.utils.parse import ArgumentParser  # type: ignore
from rxn.utilities.files import PathLike
from torch.nn.init import xavier_uniform_

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def init_parameters(model_opt, parameters):
    """Initialise extended weights

    Args:
        model_opt ([type]): original model opts
        parameters ([type]): newly created weights
    """
    if model_opt.param_init != 0.0:
        parameters.data.uniform_(-model_opt.param_init, model_opt.param_init)
    if model_opt.param_init_glorot:
        if parameters.dim() > 1:
            xavier_uniform_(parameters)
        if parameters.dim() == 1:
            # If there is only one dimension: the parameters are likely to
            # correspond to a bias vector -> set to zero.
            parameters.data.zero_()


class ModelResizer:
    def __init__(self, model_path: PathLike):
        """Resizing pretrained onmt models for training on extended vocab.

        Args:
            model_path: Path to model checkpoint
        """
        self.checkpoint = torch.load(
            model_path, map_location=lambda storage, loc: storage
        )

        self.vocab = self.checkpoint["vocab"]

        self.model_opt = ArgumentParser.ckpt_model_opts(self.checkpoint["opt"])
        ArgumentParser.update_model_opts(self.model_opt)
        ArgumentParser.validate_model_opts(self.model_opt)

        # make it CUDA independent
        self.model_opt.gpu = -1
        self.model_opt.gpu_ranks = []

        self.model = build_model(
            self.model_opt, self.model_opt, self.vocab, self.checkpoint
        )

    def extend_vocab(self, new_vocab_path: PathLike):
        """Extend vocab and size of a model using a new vocab file
        s
        Args:
            new_vocab_path: Path to new vocab file (vocab.pt generated by ONMT)
        """
        new_vocab = torch.load(
            new_vocab_path, map_location=lambda storage, loc: storage
        )

        self._extend_field_vocab(new_vocab, "src")
        self._extend_field_vocab(new_vocab, "tgt")

        self._resize_encoder()
        self._resize_decoder()
        self._resize_generator()

    def _extend_field_vocab(self, new_vocab, field: str) -> List[str]:
        """Extends model vocab with new vocab and returns the added tokens as a list."""
        # check the tokens and enlarge encoder
        # Update frequency as well (?)
        added_tokens = []
        for t in new_vocab[field].base_field.vocab.itos:
            if t not in self.vocab[field].base_field.vocab.stoi:
                added_tokens.append(t)
                self.vocab[field].base_field.vocab.itos.append(t)
                self.vocab[field].base_field.vocab.stoi[t] = (
                    len(self.vocab[field].base_field.vocab.itos) - 1
                )
        logger.debug(f"Added {len(added_tokens)} {field} tokens:\n{added_tokens}")

        return added_tokens

    def _resize_embedding(self, old_embeddings, num_added_tokens: int):
        sparse = old_embeddings.sparse
        padding_idx = old_embeddings.padding_idx
        embedding_dim = old_embeddings.embedding_dim

        weight_extension = nn.Parameter(  # type: ignore
            torch.Tensor(num_added_tokens, embedding_dim)  # type: ignore
        )  # type: ignore
        init_parameters(self.model_opt, weight_extension)
        new_weights = nn.Parameter(  # type: ignore
            torch.cat([old_embeddings.weight, weight_extension.data])
        )  # type: ignore
        new_embeddings = nn.Embedding(
            new_weights.shape[0], embedding_dim, sparse=sparse, padding_idx=padding_idx
        )

        new_embeddings.load_state_dict({"weight": new_weights})

        return new_embeddings

    def _resize_encoder(self):
        old_embeddings = self.model.encoder.embeddings.make_embedding.emb_luts[0]

        num_added_tokens = (
            len(self.vocab["src"].base_field.vocab) - old_embeddings.num_embeddings
        )

        new_embeddings = self._resize_embedding(old_embeddings, num_added_tokens)

        self.model.encoder.embeddings.make_embedding.emb_luts[0] = new_embeddings

    def _resize_decoder(self):
        old_embeddings = self.model.decoder.embeddings.make_embedding.emb_luts[0]

        num_added_tokens = (
            len(self.vocab["tgt"].base_field.vocab) - old_embeddings.num_embeddings
        )

        new_embeddings = self._resize_embedding(old_embeddings, num_added_tokens)

        self.model.decoder.embeddings.make_embedding.emb_luts[0] = new_embeddings

    def _resize_generator(self):
        old_linear = self.model.generator[0]

        num_added_tokens = (
            len(self.vocab["tgt"].base_field.vocab) - old_linear.out_features
        )

        weight_extension = nn.Parameter(  # type: ignore
            torch.Tensor(num_added_tokens, old_linear.in_features)  # type: ignore
        )
        init_parameters(self.model_opt, weight_extension)

        new_weights = nn.Parameter(  # type: ignore
            torch.cat([old_linear.weight, weight_extension.data])
        )

        bias_extension = nn.Parameter(torch.Tensor(num_added_tokens))  # type: ignore
        init_parameters(self.model_opt, bias_extension)
        new_bias = nn.Parameter(torch.cat([old_linear.bias, bias_extension.data]))  # type: ignore

        new_linear = nn.Linear(
            old_linear.in_features, len(self.vocab["tgt"].base_field.vocab)
        )
        new_linear.load_state_dict({"weight": new_weights, "bias": new_bias})

        self.model.generator[0] = new_linear

    def save_checkpoint(self, save_path: PathLike):
        """Save checkpoint of resized model

        Args:
            save_path: output path
        """
        model_state_dict = self.model.state_dict()
        model_state_dict = {
            k: v for k, v in model_state_dict.items() if "generator" not in k
        }
        generator_state_dict = self.model.generator.state_dict()

        checkpoint = {
            "model": model_state_dict,
            "generator": generator_state_dict,
            "vocab": self.vocab,
            "opt": self.model_opt,
            "optim": self.checkpoint["optim"],
        }

        logger.debug(f"Saving checkpoint to {save_path}.")

        torch.save(checkpoint, save_path)
