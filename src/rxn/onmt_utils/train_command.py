import logging
from enum import Flag
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import yaml
from rxn.utilities.files import PathLike

# from .model_introspection import get_model_rnn_size

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class RxnCommand(Flag):
    """
    Flag indicating which command(s) the parameters relate to.

    TC, TF, TCF are the combinations of the three base flags.
    This enum allows for easily checking which commands some parameters relate
    to (see Parameter and TrainingPlanner classes).
    """

    T = 1  # Train
    C = 2  # Continue training
    F = 4  # Fine-tune
    TC = 3
    TF = 5
    CF = 6
    TCF = 7


class Arg:
    """
    Represents an argument to be given for the onmt_train command.

    Attributes:
        key: argument name (i.e. what is forwarded to onmt_train, without the dash).
        default: default value that we use for that argument in the RXN universe.
            None indicates that this argument must be provided explicitly, an
            empty string is used for boolean args not requiring a value.
        needed_for: what commands this argument is needed for (train, finetune, etc.)
    """

    def __init__(self, key: str, default: Any, needed_for: RxnCommand):
        self.key = key
        self.default = default
        self.needed_for = needed_for


# See https://opennmt.net/OpenNMT-py/options/train.html
ONMT_TRAIN_ARGS: List[Arg] = [
    Arg("accum_count", "4", RxnCommand.TCF),
    Arg("adam_beta1", "0.9", RxnCommand.TF),
    Arg("adam_beta2", "0.998", RxnCommand.TF),
    Arg("batch_size", None, RxnCommand.TCF),
    Arg("batch_type", "tokens", RxnCommand.TCF),
    Arg("data", None, RxnCommand.TCF),
    Arg("decay_method", "noam", RxnCommand.TF),
    Arg("decoder_type", "transformer", RxnCommand.T),
    Arg("dropout", None, RxnCommand.TCF),
    Arg("encoder_type", "transformer", RxnCommand.T),
    Arg("global_attention", "general", RxnCommand.T),
    Arg("global_attention_function", "softmax", RxnCommand.T),
    Arg("heads", None, RxnCommand.T),
    Arg("keep_checkpoint", "-1", RxnCommand.TCF),
    Arg("label_smoothing", "0.0", RxnCommand.TCF),
    Arg("layers", None, RxnCommand.T),
    Arg("learning_rate", None, RxnCommand.TF),
    Arg("max_generator_batches", "32", RxnCommand.TCF),
    Arg("max_grad_norm", "0", RxnCommand.TF),
    Arg("normalization", "tokens", RxnCommand.TCF),
    Arg("optim", "adam", RxnCommand.TF),
    Arg("param_init", "0", RxnCommand.T),
    Arg("param_init_glorot", "", RxnCommand.T),  # note: empty means "nothing"
    Arg("position_encoding", "", RxnCommand.T),  # note: empty means "nothing"
    Arg("report_every", "1000", RxnCommand.TCF),
    Arg("reset_optim", None, RxnCommand.CF),
    Arg("hidden_size", None, RxnCommand.TF),
    Arg("save_checkpoint_steps", "5000", RxnCommand.TCF),
    Arg("save_model", None, RxnCommand.TCF),
    Arg("seed", None, RxnCommand.TCF),
    Arg("self_attn_type", "scaled-dot", RxnCommand.T),
    Arg("share_embeddings", "", RxnCommand.T),  # note: empty means "nothing"
    Arg("src_vocab", None, RxnCommand.T),
    Arg("tgt_vocab", None, RxnCommand.T),
    Arg("train_from", None, RxnCommand.CF),
    Arg("train_steps", None, RxnCommand.TCF),
    Arg("transformer_ff", None, RxnCommand.T),
    Arg("valid_batch_size", "8", RxnCommand.TCF),
    Arg("warmup_steps", None, RxnCommand.TF),
    Arg("word_vec_size", None, RxnCommand.T),
]
# TODO: (Irina) Add new v.3.5.1 arguments like lora_layers, quant_layers if necessary


class OnmtTrainCommand:
    """
    Class to build the onmt_command for training models, continuing the
    training, or finetuning.
    """

    def __init__(
        self,
        command_type: RxnCommand,
        no_gpu: bool,
        data_weights: Tuple[int, ...],
        **kwargs: Any,
    ):
        self._command_type = command_type
        self._no_gpu = no_gpu
        self._data_weights = data_weights
        self._kwargs = kwargs

    def _build_cmd(self) -> List[str]:
        """
        Build the base command.
        """
        command = ["onmt_train"]

        for arg in ONMT_TRAIN_ARGS:
            arg_given = arg.key in self._kwargs

            if self._command_type not in arg.needed_for:
                # Check that the arg was not given; then go to the next argument.
                if arg_given:
                    raise ValueError(
                        f'"{arg.key}" value given, but not necessary for {command}'
                    )
                continue

            # Case 1: something given (whether there was a default or not)
            if arg_given:
                value = str(self._kwargs[arg.key])
            # Case 2: default is None (i.e. a value is needed) but nothing was given
            elif arg.default is None:
                raise ValueError(f"No value given for {arg.key}")
            # Case 3: does not need value and nothing given
            else:
                value = str(arg.default)

            # Add the args to the command. Note: if the value is the empty string,
            # do not add anything (typically for boolean args)
            command.append(f"-{arg.key}")
            if value != "":
                command.append(value)

        command += self._args_for_gpu()
        command += self._args_for_data_weights()

        return command

    def _args_for_gpu(self) -> List[str]:
        if self._no_gpu:
            return []
        return ["-gpu_ranks", "0"]

    def _args_for_data_weights(self) -> List[str]:
        if not self._data_weights:
            return []

        n_additional_datasets = len(self._data_weights) - 1
        data_ids = preprocessed_id_names(n_additional_datasets)
        return [
            "-data_ids",
            *data_ids,
            "-data_weights",
            *(str(weight) for weight in self._data_weights),
        ]

    def cmd(self) -> List[str]:
        """
        Return the "raw" command for executing onmt_train.
        """
        return self._build_cmd()

    def is_valid_kwarg_value(self, kwarg, value) -> bool:
        # NOTE: upgrade to v.3.5.1
        # A lot of the code below is from self._build_cmd()
        # In theory, self._build_cmd() could be deprecated but to avoid breaking something,
        # it will stay until 100% sure
        # Here we jsut need the checks and not construct a command
        # TODO: assess deprecation of self._build_cmd()

        # Check if argument is in ONMT_TRAIN_ARGS
        for arg in ONMT_TRAIN_ARGS:
            if arg.key == kwarg:
                onmt_train_kwarg = arg

        try:
            onmt_train_kwarg
        except NameError:
            NameError(f"Argument {kwarg} doesn't exist in ONMT_TRAIN_ARGS.")

        # Check argument is needed for command
        if self._command_type not in onmt_train_kwarg.needed_for:
            raise ValueError(
                f'"{value}" value given for arg {kwarg}, but not necessary for command {self._command_type}'
            )
        # Check if argument has no default and needs a value
        if onmt_train_kwarg.default is None and value is None:
            raise ValueError(f"No value given for {kwarg} and needs one.")

        return True

    def save_to_config_cmd(self, config_file_path: PathLike) -> None:
        """
        Save the training config to a file.
        See https://opennmt.net/OpenNMT-py/quickstart.html part 2
        """
        # Build train config content, it will not include defaults not specified in cli
        # See structure https://opennmt.net/OpenNMT-py/quickstart.html (Step 2: Train)
        train_config: Dict[str, Any] = {}

        # GPUs
        if torch.cuda.is_available() and self._no_gpu is False:
            train_config["gpu_ranks"] = [0]

        # Dump all cli arguments to dict
        for kwarg, value in self._kwargs.items():
            if self.is_valid_kwarg_value(kwarg, value):
                train_config[kwarg] = value
            else:
                raise ValueError(f'"Value {value}" for argument {kwarg} is invalid')

        # Reformat "data" argument as in ONMT-py v.3.5.0
        path_save_prepr_data = train_config["data"]
        train_config["save_data"] = str(path_save_prepr_data)
        # TODO: update to > 1 corpus
        train_config["data"] = {"corpus_1": {}, "valid": {}}
        train_config["data"]["corpus_1"]["path_src"] = str(
            path_save_prepr_data.parent.parent
            / "data.processed.train.precursors_tokens"
        )
        train_config["data"]["corpus_1"]["path_tgt"] = str(
            path_save_prepr_data.parent.parent / "data.processed.train.products_tokens"
        )
        train_config["data"]["valid"]["path_src"] = str(
            path_save_prepr_data.parent.parent
            / "data.processed.validation.precursors_tokens"
        )
        train_config["data"]["valid"]["path_tgt"] = str(
            path_save_prepr_data.parent.parent
            / "data.processed.validation.products_tokens"
        )

        train_config["src_vocab"] = str(
            train_config["src_vocab"]
        )  # avoid posix bad format in yaml
        train_config["tgt_vocab"] = str(
            train_config["tgt_vocab"]
        )  # avoid posix bad format in yaml
        train_config["save_model"] = str(
            train_config["save_model"]
        )  # avoid posix bad format in yaml

        # Dump to config.yaml
        with open(config_file_path, "w+") as file:
            yaml.dump(train_config, file)

    @staticmethod
    def execute_from_config_cmd(config_file: PathLike) -> List[str]:
        """
        Return the command for executing onmt_train with values read from the config.
        """
        return ["onmt_train", "-config", str(config_file)]

    @classmethod
    def train(
        cls,
        batch_size: int,
        data: PathLike,
        src_vocab: Path,
        tgt_vocab: Path,
        dropout: float,
        heads: int,
        layers: int,
        learning_rate: float,
        hidden_size: int,
        save_model: PathLike,
        seed: int,
        train_steps: int,
        transformer_ff: int,
        warmup_steps: int,
        word_vec_size: int,
        no_gpu: bool,
        data_weights: Tuple[int, ...],
        keep_checkpoint: int = -1,
    ) -> "OnmtTrainCommand":
        return cls(
            command_type=RxnCommand.T,
            no_gpu=no_gpu,
            data_weights=data_weights,
            batch_size=batch_size,
            data=data,
            src_vocab=src_vocab,
            tgt_vocab=tgt_vocab,
            dropout=dropout,
            heads=heads,
            keep_checkpoint=keep_checkpoint,
            layers=layers,
            learning_rate=learning_rate,
            hidden_size=hidden_size,
            save_model=save_model,
            seed=seed,
            train_steps=train_steps,
            transformer_ff=transformer_ff,
            warmup_steps=warmup_steps,
            word_vec_size=word_vec_size,
        )

    @classmethod
    def continue_training(
        cls,
        batch_size: int,
        data: PathLike,
        dropout: float,
        save_model: PathLike,
        seed: int,
        train_from: PathLike,
        train_steps: int,
        no_gpu: bool,
        data_weights: Tuple[int, ...],
        keep_checkpoint: int = -1,
    ) -> "OnmtTrainCommand":
        return cls(
            command_type=RxnCommand.C,
            no_gpu=no_gpu,
            data_weights=data_weights,
            batch_size=batch_size,
            data=data,
            dropout=dropout,
            keep_checkpoint=keep_checkpoint,
            reset_optim="none",
            save_model=save_model,
            seed=seed,
            train_from=train_from,
            train_steps=train_steps,
        )

    @classmethod
    def finetune(
        cls,
        batch_size: int,
        data: PathLike,
        dropout: float,
        learning_rate: float,
        save_model: PathLike,
        seed: int,
        train_from: PathLike,
        train_steps: int,
        warmup_steps: int,
        no_gpu: bool,
        data_weights: Tuple[int, ...],
        report_every: int,
        save_checkpoint_steps: int,
        keep_checkpoint: int = -1,
        hidden_size: Optional[int] = None,
    ) -> "OnmtTrainCommand":
        if hidden_size is None:
            # In principle, the rnn_size should not be needed for finetuning. However,
            # when resetting the decay algorithm for the learning rate, this value
            # is necessary - and does not get it from the model checkpoint (OpenNMT bug).
            # rnn_size = get_model_rnn_size(train_from)
            logger.info(
                f"Loaded the value of hidden_size from the model: {hidden_size}."
            )

        return cls(
            command_type=RxnCommand.F,
            no_gpu=no_gpu,
            data_weights=data_weights,
            batch_size=batch_size,
            data=data,
            dropout=dropout,
            keep_checkpoint=keep_checkpoint,
            learning_rate=learning_rate,
            reset_optim="all",
            hidden_size=hidden_size,
            save_model=save_model,
            seed=seed,
            train_from=train_from,
            train_steps=train_steps,
            warmup_steps=warmup_steps,
            report_every=report_every,
            save_checkpoint_steps=save_checkpoint_steps,
        )


def preprocessed_id_names(n_additional_sets: int) -> List[str]:
    """Get the names of the ids for the datasets used in multi-task training
    with OpenNMT.

    Args:
        n_additional_sets: how many sets there are in addition to the main set.
    """
    return ["main_set"] + [f"additional_set_{i+1}" for i in range(n_additional_sets)]
