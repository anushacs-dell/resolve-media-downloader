
import os
import sys


RESOLVE_MODULE_PATH = (
    "/Library/Application Support/Blackmagic Design/"
    "DaVinci Resolve/Developer/Scripting/Modules"
)

RESOLVE_FUSION_PATH = (
    "/Applications/DaVinci Resolve/"
    "DaVinci Resolve.app/Contents/Libraries/Fusion"
)


MEDIA_BINS = {
    "image": "Images",
    "audio": "Audio",
    "video": "Video",
}


def get_resolve():
    """Connect to the currently running DaVinci Resolve instance."""

    if RESOLVE_MODULE_PATH not in sys.path:
        sys.path.append(RESOLVE_MODULE_PATH)

    if RESOLVE_FUSION_PATH not in sys.path:
        sys.path.append(RESOLVE_FUSION_PATH)

    try:
        import DaVinciResolveScript as dvr_script
    except ImportError as error:
        raise RuntimeError(
            "Could not load DaVinci Resolve scripting API."
        ) from error

    resolve = dvr_script.scriptapp("Resolve")

    if resolve is None:
        raise RuntimeError(
            "Could not connect to DaVinci Resolve."
        )

    return resolve


def find_media_bin(folder, bin_name):
    """Find an existing Media Pool bin recursively."""

    for subfolder in folder.GetSubFolderList() or []:
        if subfolder.GetName().strip().lower() == bin_name.lower():
            return subfolder

        result = find_media_bin(subfolder, bin_name)

        if result:
            return result

    return None


def get_or_create_media_bin(media_pool, bin_name):
    """Reuse an existing bin or create it if it does not exist."""

    root_folder = media_pool.GetRootFolder()

    media_bin = find_media_bin(root_folder, bin_name)

    if media_bin is None:
        media_bin = media_pool.AddSubFolder(
            root_folder,
            bin_name,
        )

    if media_bin is None:
        raise RuntimeError(
            f"Could not find or create the {bin_name} bin."
        )

    return media_bin


def import_to_media_bin(file_path, media_type):
    """Import downloaded media into its corresponding Resolve bin."""

    if not os.path.isfile(file_path):
        raise RuntimeError(
            f"Downloaded file does not exist:\n{file_path}"
        )

    media_type = media_type.strip().lower()

    if media_type not in MEDIA_BINS:
        raise ValueError(
            f"Unsupported media type: {media_type}"
        )

    bin_name = MEDIA_BINS[media_type]

    resolve = get_resolve()

    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()

    if project is None:
        raise RuntimeError(
            "No DaVinci Resolve project is currently open."
        )

    media_pool = project.GetMediaPool()

    # Find the existing bin recursively or create it.
    media_bin = get_or_create_media_bin(
        media_pool,
        bin_name,
    )

    # Import the file into the correct bin.
    media_pool.SetCurrentFolder(media_bin)

    imported_items = media_pool.ImportMedia(
        [os.path.abspath(file_path)]
    )

    if not imported_items:
        raise RuntimeError(
            f"DaVinci Resolve could not import the media into {bin_name}."
        )

    return imported_items[0]


def import_to_audio_bin(file_path):
    """Backward-compatible Audio import function."""

    return import_to_media_bin(file_path, "audio")
