import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import warnings
import boto3
from botocore.config import Config
import imageio_ffmpeg
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException

Image.MAX_IMAGE_PIXELS = 20_000_000


class Storage:
    def __init__(self, settings):
        self.settings = settings
        self.root = settings.data_dir / 'media'
        self.root.mkdir(parents=True, exist_ok=True)
        # Custom S3 endpoints (including Supabase) use a path prefix and SigV4.
        # Optional AWS checksums are not universally supported by compatible stores.
        config = Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'},
            request_checksum_calculation='when_required',
            response_checksum_validation='when_required',
        ) if settings.s3_endpoint else None
        self.client = boto3.client('s3', endpoint_url=settings.s3_endpoint or None, config=config) if settings.storage == 's3' else None

    def put(self, key, path, mime):
        if self.client:
            self.client.upload_file(str(path), self.settings.s3_bucket, key, ExtraArgs={'ContentType': mime})
        else:
            target = self.root / key
            shutil.copyfile(path, target)
            target.chmod(0o600)

    def delete(self, key):
        if self.client:
            self.client.delete_object(Bucket=self.settings.s3_bucket, Key=key)
        else:
            (self.root / key).unlink(missing_ok=True)

    def presigned(self, key):
        return self.client.generate_presigned_url('get_object', Params={'Bucket': self.settings.s3_bucket, 'Key': key}, ExpiresIn=60)


def validate_media(path: Path, content_type: str):
    """Decode actual content; strip EXIF. Never trust a filename or browser MIME alone."""
    if content_type in {'image/jpeg', 'image/png', 'image/webp'}:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(path) as im:
                    if im.format not in {'JPEG', 'PNG', 'WEBP'}:
                        raise ValueError('Unsupported image')
                    im.load()
                    image = ImageOps.exif_transpose(im).convert('RGB')
                    image.thumbnail((2560, 2560))
                    image.save(path, format='JPEG', quality=88)
            return 'image', 'image/jpeg'
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(422, 'Не удалось прочитать фото. Используйте JPEG, PNG или WebP.')
    if content_type not in {'video/mp4', 'video/webm', 'video/quicktime'}:
        raise HTTPException(415, 'Поддерживаются JPEG, PNG, WebP и короткое видео MP4, WebM или MOV.')
    header = path.read_bytes()[:32]
    if b'ftyp' not in header and not header.startswith(b'\x1a\x45\xdf\xa3'):
        raise HTTPException(422, 'Файл не является поддерживаемым видео.')
    binary = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        probe = subprocess.run([binary, '-hide_banner', '-protocol_whitelist', 'file,pipe', '-i', str(path)], capture_output=True, timeout=15)
        info = probe.stderr.decode(errors='replace')
        duration = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', info)
        if not duration or 'Video:' not in info:
            raise ValueError('No video stream')
        hours, minutes, seconds = map(float, duration.groups())
        if hours * 3600 + minutes * 60 + seconds > 30.5:
            raise HTTPException(422, 'Видео должно быть не длиннее 30 секунд.')
        dimensions = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b', info)
        if not dimensions or int(dimensions[1]) * int(dimensions[2]) > 3840 * 2160:
            raise ValueError('Unsupported resolution')
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False, dir=path.parent) as tmp:
            output = Path(tmp.name)
        try:
            result = subprocess.run([binary, '-v', 'error', '-nostdin', '-y', '-threads', '2', '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', '0:v:0', '-an', '-map_metadata', '-1', '-t', '30.5', '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2', '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '27', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)], capture_output=True, timeout=90)
            if result.returncode:
                raise ValueError('Invalid video')
            shutil.move(output, path)
        finally:
            output.unlink(missing_ok=True)
        return 'video', 'video/mp4'
    except (ValueError, subprocess.TimeoutExpired, OSError):
        raise HTTPException(422, 'Не удалось обработать видео. Попробуйте короткий MP4 или фотографию.')
