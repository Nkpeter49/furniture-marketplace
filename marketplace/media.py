"""Private, normalized image uploads for profile and listing media."""

from io import BytesIO
import re
import uuid
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_SIDE = 6_000
STORED_IMAGE_MAX_SIDE = 1_600
SAFE_FILENAME = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png)$")


class InvalidImage(ValueError):
    """The uploaded bytes are not a supported, safely bounded image."""


def prepare_image(upload) -> tuple[bytes, str]:
    """Decode a bounded image and re-encode it, dropping metadata and input names."""
    if upload is None or not getattr(upload, "filename", ""):
        raise InvalidImage("Choose an image file.")
    raw = upload.read(MAX_IMAGE_BYTES + 1)
    if not raw:
        raise InvalidImage("The selected image is empty.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise InvalidImage("Each image must be 5 MB or smaller.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as check:
                if check.format not in {"JPEG", "PNG", "WEBP"}:
                    raise InvalidImage("Use a JPEG, PNG, or WebP image.")
                if getattr(check, "is_animated", False):
                    raise InvalidImage("Animated images are not supported.")
                width, height = check.size
                if (
                    width < 1 or height < 1
                    or width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise InvalidImage("Image dimensions must be at most 6000 pixels per side and 16 megapixels total.")
                check.verify()

            with Image.open(BytesIO(raw)) as image:
                image.load()
                image = ImageOps.exif_transpose(image)
                if max(image.size) > STORED_IMAGE_MAX_SIDE:
                    image.thumbnail(
                        (STORED_IMAGE_MAX_SIDE, STORED_IMAGE_MAX_SIDE),
                        Image.Resampling.LANCZOS,
                    )
                has_alpha = image.mode in {"RGBA", "LA"} or (
                    image.mode == "P" and "transparency" in image.info
                )
                if has_alpha:
                    normalized = image.convert("RGBA")
                    output_format, suffix = "PNG", ".png"
                else:
                    normalized = image.convert("RGB")
                    output_format, suffix = "JPEG", ".jpg"
                output = BytesIO()
                if output_format == "JPEG":
                    normalized.save(output, format="JPEG", quality=88, optimize=True)
                else:
                    normalized.save(output, format="PNG", optimize=True)
                encoded = output.getvalue()
    except InvalidImage:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise InvalidImage("That image could not be safely opened. Choose a valid JPEG, PNG, or WebP image.") from exc

    if len(encoded) > MAX_IMAGE_BYTES:
        raise InvalidImage("The processed image is too large. Choose a smaller image.")
    return encoded, suffix


def store_image(encoded: bytes, suffix: str, instance_path: str) -> str:
    """Write to a private instance folder using an unpredictable server filename."""
    if suffix not in {".jpg", ".png"}:
        raise ValueError("Unsupported normalized image format")
    directory = Path(instance_path) / "media"
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    target_path = directory / filename
    try:
        with target_path.open("xb") as target:
            target.write(encoded)
            target.flush()
    except OSError:
        target_path.unlink(missing_ok=True)
        raise
    return filename


def delete_image(filename: str | None, instance_path: str) -> None:
    """Remove only a generated media key; arbitrary paths are never accepted."""
    if not filename or not SAFE_FILENAME.fullmatch(filename):
        return
    (Path(instance_path) / "media" / filename).unlink(missing_ok=True)


def image_path(filename: str | None, instance_path: str) -> Path | None:
    if not filename or not SAFE_FILENAME.fullmatch(filename):
        return None
    path = Path(instance_path) / "media" / filename
    return path if path.is_file() else None
