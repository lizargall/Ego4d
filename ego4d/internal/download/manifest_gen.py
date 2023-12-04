"""
This scripts generates the listing of files that the CLI will download.

It does so by partitioning a list of ManifestEntry's into parts. See the
`manifests` dict below; the keys are the names of each part of the dataset.

This should only be used internally by the Eng Team of the EgoExo dataset.
"""

import json
import os
from collections import defaultdict

from ego4d.internal.download.manifest import (
    manifest_dumps,
    ManifestEntry,
    PathSpecification,
)

from ego4d.internal.s3 import S3Downloader
from iopath.common.file_io import PathManager
from iopath.common.s3 import S3PathHandler
from tqdm.auto import tqdm

pathmgr = PathManager()  # for downloading files
pathmgr.register_handler(S3PathHandler(profile="default"))


release_dir = "s3://ego4d-consortium-sharing/egoexo/releases/dev"

egoexo = {
    "takes": os.path.join(release_dir, "takes.json"),
    "takes_dropped": os.path.join(release_dir, "takes_dropped.json"),
    "captures": os.path.join(release_dir, "captures.json"),
    "physical_setting": os.path.join(release_dir, "physical_setting.json"),
    "participants": os.path.join(release_dir, "participants.json"),
    "visual_objects": os.path.join(release_dir, "visual_objects.json"),
}


manifests = {
    "metadata": [],
    "takes": [],
    "takes_dropped": [],
    "captures": [],
    "trajectory": [],
    "eye_gaze": [],
    "point_cloud": [],
    "capture_raw_stitched_videos": [],
    "capture_raw_vrs": [],
    "annotations": [],
    "ego_pose_pseudo_gt": [],
    "features/omnivore_video": [],
    "downscaled_takes": [],
    "narrate_and_act_transc": [],
}


downloader = S3Downloader("default")
print("Downloading metadata")
for k, out_path in tqdm(egoexo.items()):
    s3_path = os.path.join(release_dir, f"{k}.json")
    print(s3_path, out_path)
    paths = [PathSpecification(s3_path, f"{k}.json")]
    manifests["metadata"].append(
        ManifestEntry(
            uid=k,
            paths=paths,
        )
    )

for k, v in egoexo.items():
    egoexo[k] = json.load(pathmgr.open(v))


take_name_to_uid = {
    t["root_dir"]: t["take_uid"] for t in (egoexo["takes"] + egoexo["takes_dropped"])
}

for manifest_key in ["takes", "takes_dropped"]:
    for t in egoexo[manifest_key]:
        root_dir = os.path.join("takes", t["root_dir"])
        paths = []
        for streams in t["frame_aligned_videos"].values():
            for vid in streams.values():
                # TODO: check
                if vid["_s3_path"] is None:
                    continue
                uid = vid["clip_uid"]
                paths.append(
                    PathSpecification(
                        source_path=vid["_s3_path"],
                        relative_path=os.path.join(root_dir, vid["relative_path"]),
                    )
                )

        manifests[manifest_key].append(
            ManifestEntry(
                uid=t["take_uid"],
                paths=paths,
            )
        )


for c in tqdm(egoexo["captures"]):
    s3_bucket = c["_s3_root_dir"].split("/")[2]
    root_dir = os.path.join("captures", c["root_dir"])
    traj_fp = c["_trajectory_s3_dir"]
    post_fp = c["_postsurvery_s3_path"]
    eye_gaze_fp = c["_gaze_s3_dir"]
    timesync_fp = c["_timesync_s3_path"]
    ts_dir = os.path.join(c["_s3_root_dir"], "timesync")
    traj_files = downloader.ls(traj_fp + "/", max_keys=1000) if traj_fp else []
    eye_gaze_files = (
        downloader.ls(eye_gaze_fp + "/", max_keys=1000) if eye_gaze_fp else []
    )
    ts_files = downloader.ls(ts_dir + "/", max_keys=1000)

    traj_paths = []
    point_cloud_paths = []
    for bn, s3_path in traj_files:
        if "global_points" in bn:
            point_cloud_paths.append(
                PathSpecification(
                    source_path=s3_path,
                    relative_path=os.path.join(root_dir, "trajectory", bn),
                )
            )
        else:
            traj_paths.append(
                PathSpecification(
                    source_path=s3_path,
                    relative_path=os.path.join(root_dir, "trajectory", bn),
                )
            )

    manifests["trajectory"].append(
        ManifestEntry(
            uid=c["capture_uid"],
            paths=traj_paths,
        )
    )
    manifests["point_cloud"].append(
        ManifestEntry(
            uid=c["capture_uid"],
            paths=point_cloud_paths,
        )
    )
    eye_gaze_paths = []
    for bn, s3_path in eye_gaze_files:
        eye_gaze_paths.append(
            PathSpecification(
                source_path=s3_path,
                relative_path=os.path.join(root_dir, "eye_gaze", bn),
            )
        )
    manifests["eye_gaze"].append(
        ManifestEntry(
            uid=c["capture_uid"],
            paths=eye_gaze_paths,
        )
    )

    capture_paths = []
    if post_fp is not None:
        capture_paths.append(
            PathSpecification(
                source_path=post_fp,
                relative_path=os.path.join(root_dir, "post_surveys.csv"),
            )
        )

    if timesync_fp is not None:
        capture_paths.append(
            PathSpecification(
                source_path=timesync_fp,
                relative_path=os.path.join(root_dir, "timesync.csv"),
            )
        )
    for bn, s3_path in ts_files:
        capture_paths.append(
            PathSpecification(
                source_path=s3_path,
                relative_path=os.path.join(root_dir, "timesync", f"{bn}"),
            )
        )

    manifests["captures"].append(
        ManifestEntry(
            uid=c["capture_uid"],
            paths=capture_paths,
        )
    )

    stitched_paths = []
    vrs_paths = []
    for x in c["cameras"]:
        if x["device_type"] == "aria":
            vrs_paths.append(
                PathSpecification(
                    source_path=x["_s3_path"],
                    relative_path=os.path.join(root_dir, x["relative_path"]),
                )
            )
        else:
            stitched_paths.append(
                PathSpecification(
                    source_path=x["_s3_path"],
                    relative_path=os.path.join(root_dir, x["relative_path"]),
                )
            )
    manifests["capture_raw_vrs"].append(
        ManifestEntry(
            uid=c["capture_uid"],
            paths=vrs_paths,
        )
    )

    manifests["capture_raw_stitched_videos"].append(
        ManifestEntry(
            uid=c["capture_uid"],
            paths=stitched_paths,
        )
    )

annotations = downloader.ls(os.path.join(release_dir, "annotations/"))
for bn, s3_path in annotations:
    if len(bn) == 0:
        continue
    if bn == "manifest.json":
        continue

    manifests["annotations"].append(
        ManifestEntry(
            uid="_".join(bn.split("_")[:-1]),
            paths=[
                PathSpecification(
                    source_path=s3_path,
                    relative_path=f"annotations/{bn}",
                )
            ],
        )
    )

egopose_part_subdirs = {
    "annotations": {
        "subdirs": [
            "annotation",
            "camera_pose",
        ],
        "take_uid_as_key": False,
    },
    "ego_pose_pseudo_gt": {
        "subdirs": ["automatic"],
        "take_uid_as_key": True,
    },
}
egopose_base_dir = os.path.join(release_dir, "annotations/ego_pose_latest/")
for body_type in ["body", "hand"]:
    subdir = os.path.join(egopose_base_dir, body_type)

    annotation_files = []
    for manifest_key, metadata in egopose_part_subdirs.items():

        for ann_dir in metadata["subdirs"]:
            relative_subdir = os.path.join("annotations/ego_pose/", body_type, ann_dir)
            ann_files = downloader.ls(os.path.join(subdir, ann_dir + "/"))
            for bn, s3_path in ann_files:
                if len(bn) == 0:
                    continue
                if bn == "manifest.json":
                    continue
                take_uid = os.path.splitext(bn)[0]
                # TODO: partition ManifestEntry with more variables such that
                # we don't need to join strings in this manner
                uid = (
                    take_uid
                    if metadata["take_uid_as_key"]
                    else "_".join(["ego_pose", body_type, ann_dir, take_uid])
                )
                manifests[manifest_key].append(
                    ManifestEntry(
                        # e.g.
                        # - body_annotation_<take_uid>
                        # - body_hand_<take_uid>
                        uid=uid,
                        paths=[
                            PathSpecification(
                                source_path=s3_path,
                                relative_path=f"{relative_subdir}/{bn}",
                            )
                        ],
                    )
                )

downscaled_takes = downloader.ls(
    os.path.join(release_dir, "downscaled_takes/"), recursive=True
)
by_take = defaultdict(list)
for bn, path in downscaled_takes:
    take_name = path.split("downscaled_takes/")[1].split("/")[0]
    if take_name not in take_name_to_uid:
        continue
    take_uid = take_name_to_uid[take_name]
    by_take[take_uid].append(
        PathSpecification(
            source_path=path,
            relative_path=f"takes/{take_name}/frame_aligned_videos/downscaled/{bn}",
        )
    )

for take_uid, paths in by_take.items():
    manifests["downscaled_takes"].append(
        ManifestEntry(
            uid=take_uid,
            paths=paths,
        )
    )

for feature_name in ["omnivore_video"]:
    feature_files = downloader.ls(
        os.path.join(release_dir, "features/", feature_name + "/")
    )
    by_take = defaultdict(list)
    for file_name, path in feature_files:
        if file_name.endswith("yaml"):
            manifests[f"features/{feature_name}"].append(
                ManifestEntry(
                    uid="config",
                    paths=[
                        PathSpecification(
                            source_path=path,
                            relative_path=f"features/{feature_name}/{file_name}",
                        )
                    ],
                )
            )
            continue

        if file_name == "" or file_name == "manifest.json":
            continue
        take_uid, cam_id, stream_id = file_name.split("_")
        by_take[take_uid].append(
            PathSpecification(
                source_path=path,
                relative_path=f"features/{feature_name}/{file_name}",
            )
        )

    for take_uid, paths in by_take.items():
        manifests[f"features/{feature_name}"].append(
            ManifestEntry(
                uid=take_uid,
                paths=paths,
            )
        )

na_transc = downloader.ls(
    os.path.join(release_dir, "annotations/narrate_and_act_transc/"), recursive=True
)
by_take = defaultdict(list)
for file_name, path in na_transc:
    if file_name == ".DS_Store":
        continue
    tn = os.path.splitext(file_name)[0]
    if tn not in take_name_to_uid:
        continue
    take_uid = take_name_to_uid[tn]
    by_take[take_uid].append(
        PathSpecification(
            source_path=path,
            relative_path=f"annotations/narrate_and_act_transc/{tn}/{file_name}",
        )
    )

for take_uid, paths in by_take.items():
    manifests["narrate_and_act_transc"].append(
        ManifestEntry(
            uid=take_uid,
            paths=paths,
        )
    )


for k, v in manifests.items():
    out_dir = os.path.join(release_dir, f"{k}/")
    manifest_file = os.path.join(release_dir, k, "manifest.json")
    print(k, len(v))
    print(f"will output to: {out_dir}")
    print(f"{manifest_file}")
    pathmgr.mkdirs(out_dir, exist_ok=True)
    pathmgr.rm(manifest_file)
    with pathmgr.open(manifest_file, "w") as out_f:
        json_data = manifest_dumps(v)
        out_f.write(json_data)
