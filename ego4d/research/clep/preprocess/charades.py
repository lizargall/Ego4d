import torch
import h5py
from tqdm.auto import tqdm
from omegaconf import OmegaConf

from ego4d.research.clep.config import (
    TrainConfig,
    EgoCharadePreprocessConfig,
)
from ego4d.research.clep.preprocess.common import (
    get_language_model,
)
from ego4d.features.config import (
    FeatureExtractConfig,
    Video,
    load_model,
)
from ego4d.features.extract_features import extract_features
from ego4d.features.inference import (
    _video_info as video_info,
)



def preprocess_ego_charade(config: TrainConfig, char_config: EgoCharadePreprocessConfig):
    out_dir = config.pre_config.root_dir
    os.makedirs(out_dir, exist_ok=True)

    df = pd.read_csv(char_config.set_path)

    root_path = char_config.video_root_path
    feature_extract_config = OmegaConf.load(config.input_config.feature_extract_config_path)

    out_path = os.path.join(config.root_dir, char_config.out_path)

    class_desc_path = char_config.class_desc_path
    class_name_df = pd.read_csv(class_desc_path, header=None)
    class_names = [" ".join(x[1].split(" ")[1:]) for x in class_name_df.itertuples()]

    def get_label_name(x):
        x.replace("Someone", "")
        x.replace("is", "")
        return x.lower()

    sentences_ego = [
        f"Camera wearer is {get_label_name(clazz)}"
        for clazz in class_names
    ]

    sentences_non_ego = [
        f"The person in this video is {get_label_name(clazz)}"
        for clazz in class_names
    ]
    model = get_language_model(config)
    # pyre-ignore
    label_name_fv = model.encode(
        class_names,
        device="cuda",
        show_progress_bar=True,
    )
    # pyre-ignore
    sent_ego_fv = model.encode(
        sentences_ego,
        device="cuda",
        show_progress_bar=True,
    )
    # pyre-ignore
    sent_non_ego = model.encode(
        sentences_non_ego,
        device="cuda",
        show_progress_bar=True,
    )
    torch.save({
        "labels": label_name_fv,
        "sent_ego_fv": sent_ego_fv,
        "sent_non_ego_fv": sent_non_ego,
    }, char_config.out_label_path)
    video_path_ids = [(os.path.join(root_path, f"{row.id}.mp4"), row.id) for row in df.itertuples()]
    video_path_ids = [vp for vp in video_path_ids if os.path.exists(vp[0])]

    batches = batch_it(video_path_ids, char_config.num_vids_per_machine)
    executor = create_executor(char_config, len(batches))
    map_fn = functools.partial(
        _preprocess_ego_charade,
        feature_extract_config=feature_extract_config,
    )

    jobs = executor.map_array(map_fn, batches)

    with h5py.File(out_path, "w") as out_f:
        for j in tqdm(jobs):
            feat = j.result()
            for uid, ret in feat.items():
                out_f.create_dataset(uid, data=ret["all_fvs"].numpy())


def _preprocess_ego_charade(video_path_ids, feature_extract_config):
    model = load_model(feature_extract_config, patch_final_layer=True)

    ret = {}
    for path, uid in tqdm(video_path_ids):
        predictions = _extract_features(path, model, feature_extract_config)
        assert predictions is not None
        ret[uid] = {
            "features": predictions.result[path],
        }
    return ret
