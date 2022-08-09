#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.

"""
Command line tool to download Ego4D datasets.

Examples:
      python -m cli \
        -i "s3://ego4d-cmu/metadata_v27"
"""
import logging
import os
from typing import List

import boto3
from ego4d.cli.universities import UNIV_TO_BUCKET

from ego4d.internal.config import (
    unis,
    meta_path,
    Config,
    config_from_args,
    validate_config,
)

def main_cfg(cfg: Config) -> None:

    validated_cfg = validate_config(cfg)

    # This service resource in the default session will be used for general light-weight
    # requests on the main thread, such as downloading the video manifests and getting
    # S3 object metadata
    # s3 = boto3.session.Session(profile_name=validated_cfg.aws_profile_name).resource(
    #     "s3"
    # )
    s3 = boto3.client('s3')
    if cfg.validate_all:
        for u in unis:
            path = f"s3://{UNIV_TO_BUCKET[u]}/{meta_path[u]}"
            validate_all(path, s3)
    else:
        validate_all(cfg.input_directory, s3)

def main() -> None:
    config = config_from_args()
    main_cfg(config)


if __name__ == "__main__":
    main()
