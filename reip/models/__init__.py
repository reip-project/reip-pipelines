# from pkg_resources import resource_filename
# import pooch
#
#
# _path = os.environ.get("LIBROSA_DATA_DIR", pooch.os_cache("librosa"))
# _DOGGY = pooch.create(
#     __data_path, base_url="https://librosa.org/data/audio/", registry=None
# )
#
# _DOGGY.load_registry(
#     resource_filename(__name__, str(Path("example_data") / "registry.txt"))
# )
#
# with open(
#     resource_filename(__name__, str(Path("example_data") / "index.json")), "r"
# ) as fdesc:
#     __TRACKMAP = json.load(fdesc)
