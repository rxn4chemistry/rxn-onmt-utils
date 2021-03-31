# LICENSED INTERNAL CODE. PROPERTY OF IBM.
# IBM Research Zurich Licensed Internal Code
# (C) Copyright IBM Corp. 2021
# ALL RIGHTS RESERVED

import torch
import logging

import torch.nn as nn
from torch.nn.init import xavier_uniform_

from onmt.utils.parse import ArgumentParser
from onmt.model_builder import build_model

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


class ModelResizer:

    def __init__(self, model_path: str, use_gpu: bool = False):
        """Resizing pretrained onmt models for training on extended vocab.

        Args:
            model_path (str): Path to model checkpoint
            use_gpu (bool): Modify model_opt to not use a GPU.  
        """
        self.checkpoint = torch.load(
            model_path, map_location=lambda storage, loc: storage
        )

        self.vocab = self.checkpoint['vocab']

        self.model_opt = ArgumentParser.ckpt_model_opts(self.checkpoint["opt"])
        ArgumentParser.update_model_opts(self.model_opt)
        ArgumentParser.validate_model_opts(self.model_opt)

        if not use_gpu:
            self.model_opt.gpu = -1
            self.model_opt.gpu_ranks = []

        self.model = build_model(
            self.model_opt, self.model_opt, self.vocab, self.checkpoint
        )

    def extend_vocab(self, new_vocab_path: str, share_vocab: bool = True):
        """Extend vocab and size of a model using a new vocab file

        Args:
            new_vocab_path (str): Path to new vocab file
            share_vocab (bool, optional): [description]. Defaults to True.
        """
        new_vocab = torch.load(
            new_vocab_path, map_location=lambda storage, loc: storage
        )

        added_src_tokens = self._extend_field_vocab(new_vocab, 'src')

        if not share_vocab:
            added_tgt_tokens = self._extend_field_vocab(new_vocab, 'tgt')
        else:
            added_tgt_tokens = added_src_tokens

        self._resize_encoder(len(added_src_tokens))
        self._resize_decoder(len(added_tgt_tokens))
        self._resize_generator(len(added_tgt_tokens))

    def _extend_field_vocab(self, new_vocab, field: str):
        # check the tokens and enlarge encoder
        # Update frequency as well (?)
        added_tokens = []
        for t in new_vocab[field].base_field.vocab.itos:
            if t not in self.vocab[field].base_field.vocab.stoi:
                added_tokens.append(t)
                self.vocab[field].base_field.vocab.itos.append(t)
                self.vocab[field].base_field.vocab.stoi[t] = len(
                    self.vocab[field].base_field.vocab.itos
                ) - 1
        logger.info(
            f'Added {len(added_tokens)} {field} tokens:\n{added_tokens}'
        )

        return added_tokens

    def _resize_embedding(self, old_embeddings, num_added_tokens: int):
        sparse = old_embeddings.sparse
        padding_idx = old_embeddings.padding_idx
        embedding_dim = old_embeddings.embedding_dim

        weight_extension = nn.Parameter(
            torch.Tensor(num_added_tokens, embedding_dim)
        )
        init_parameters(self.model_opt, weight_extension)
        new_weights = nn.Parameter(
            torch.cat([old_embeddings.weight, weight_extension.data])
        )
        new_embeddings = nn.Embedding(
            new_weights.shape[0],
            embedding_dim,
            sparse=sparse,
            padding_idx=padding_idx
        )

        new_embeddings.load_state_dict({'weight': new_weights})

        return new_embeddings

    def _resize_encoder(self, num_added_tokens: int):
        old_embeddings = self.model.encoder.embeddings.make_embedding.emb_luts[
            0]

        new_embeddings = self._resize_embedding(
            old_embeddings, num_added_tokens
        )

        self.model.encoder.embeddings.make_embedding.emb_luts[
            0] = new_embeddings

    def _resize_decoder(self, num_added_tokens: int):
        old_embeddings = self.model.decoder.embeddings.make_embedding.emb_luts[
            0]

        new_embeddings = self._resize_embedding(
            old_embeddings, num_added_tokens
        )

        self.model.decoder.embeddings.make_embedding.emb_luts[
            0] = new_embeddings

    def _resize_generator(self, num_added_tokens: int):
        old_linear = self.model.generator[0]

        weight_extension = nn.Parameter(
            torch.Tensor(num_added_tokens, old_linear.in_features)
        )
        init_parameters(self.model_opt, weight_extension)

        new_weights = nn.Parameter(
            torch.cat([old_linear.weight, weight_extension.data])
        )

        bias_extension = nn.Parameter(torch.Tensor(num_added_tokens))
        init_parameters(self.model_opt, bias_extension)
        new_bias = nn.Parameter(
            torch.cat([old_linear.bias, bias_extension.data])
        )

        new_linear = nn.Linear(
            old_linear.in_features, len(self.vocab["tgt"].base_field.vocab)
        )
        new_linear.load_state_dict({'weight': new_weights, 'bias': new_bias})

        self.model.generator[0] = new_linear

    def save_checkpoint(self, save_path: str):
        """Save checkpoint of resized model

        Args:
            save_path (str): output path
        """
        model_state_dict = self.model.state_dict()
        model_state_dict = {
            k: v
            for k, v in model_state_dict.items() if 'generator' not in k
        }
        generator_state_dict = self.model.generator.state_dict()

        checkpoint = {
            'model': model_state_dict,
            'generator': generator_state_dict,
            'vocab': self.vocab,
            'opt': self.model_opt,
            'optim': self.checkpoint['optim'],
        }

        logger.info(f'Saving checkpoint to {save_path}.')

        torch.save(checkpoint, save_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    vocab_path = '../../sulfonium-synthesis.vocab.pt'
    model_path = '../../det_MIT_mixed_v2_MT384_settings_r42_step_250000.pt'
    resizer = ModelResizer(model_path)

    resizer.extend_vocab(vocab_path)

    resizer.save_checkpoint('../../resized_model.pt')
