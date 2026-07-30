import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import render
from django.utils.text import get_valid_filename
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from PIL import Image, UnidentifiedImageError

from ..image_optimization import validate_image_dimensions

MAX_CONVERTER_UPLOAD_SIZE = 25 * 1024 * 1024
MAX_CONVERTER_OUTPUT_SIZE = 50 * 1024 * 1024
OFFICE_CONVERTER_MEMORY_LIMIT = 768 * 1024 * 1024
OFFICE_CONVERTER_CPU_SECONDS = 40
OFFICE_TO_PDF_EXTENSIONS = {
    ".doc",
    ".docx",
    ".odt",
    ".rtf",
    ".txt",
    ".html",
    ".htm",
    ".csv",
    ".xls",
    ".xlsx",
    ".ods",
    ".ppt",
    ".pptx",
    ".odp",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
IMAGE_TARGETS = {"png", "jpg", "webp", "pdf"}
TARGET_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
}


class ConversionResourceLimitError(RuntimeError):
    pass


def _format_file_size(size):
    size = float(size or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024


def _office_converter_binary():
    return shutil.which("libreoffice") or shutil.which("soffice")


def _write_uploaded_file(uploaded_file, destination):
    written = 0
    with destination.open("wb") as target:
        for chunk in uploaded_file.chunks():
            written += len(chunk)
            if written > MAX_CONVERTER_UPLOAD_SIZE:
                raise ConversionResourceLimitError(_("Die Datei ist zu gross."))
            target.write(chunk)


def _download_response(output_path, filename, target, *, cleanup):
    response = FileResponse(
        output_path.open("rb"),
        as_attachment=True,
        filename=filename,
        content_type=TARGET_CONTENT_TYPES[target],
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    response._resource_closers.append(cleanup)
    return response


def _resource_limited_office_command(command):
    prlimit = shutil.which("prlimit")
    if not prlimit:
        return command
    return [
        prlimit,
        f"--cpu={OFFICE_CONVERTER_CPU_SECONDS}",
        f"--as={OFFICE_CONVERTER_MEMORY_LIMIT}",
        f"--fsize={MAX_CONVERTER_OUTPUT_SIZE}",
        "--nofile=64",
        "--nproc=64",
        "--",
        *command,
    ]


def _convert_office_to_pdf(source_path, output_dir):
    binary = _office_converter_binary()
    if not binary:
        raise RuntimeError(_("LibreOffice ist auf dem Server nicht installiert."))

    profile_dir = output_dir / "libreoffice-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    before = set(output_dir.glob("*.pdf"))
    command = [
        binary,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--nodefault",
        "--norestore",
        f"-env:UserInstallation=file://{profile_dir}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(source_path),
    ]
    command = _resource_limited_office_command(command)
    converter_env = {
        "HOME": str(profile_dir),
        "TMPDIR": str(output_dir),
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C.UTF-8",
        "SAL_USE_VCLPLUGIN": "svp",
    }
    for key in ("SystemRoot", "WINDIR"):
        if os.environ.get(key):
            converter_env[key] = os.environ[key]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=45,
            env=converter_env,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(_("Die Konvertierung hat zu lange gedauert.")) from exc

    after = set(output_dir.glob("*.pdf"))
    created = sorted(after - before, key=lambda item: item.stat().st_mtime, reverse=True)
    expected = output_dir / f"{source_path.stem}.pdf"

    if result.returncode == 0 and expected.exists():
        return expected

    if result.returncode == 0 and created:
        return created[0]

    partial_outputs = [path for path in [expected, *created] if path.exists()]
    if any(path.stat().st_size >= MAX_CONVERTER_OUTPUT_SIZE for path in partial_outputs):
        raise ConversionResourceLimitError(
            _("Die konvertierte Datei ist zu gross. Maximal erlaubt sind %(size)s.") % {
                "size": _format_file_size(MAX_CONVERTER_OUTPUT_SIZE),
            }
        )

    error_text = (result.stderr or result.stdout or b"").decode("utf-8", errors="ignore").strip()
    if error_text:
        raise RuntimeError(_("LibreOffice konnte die Datei nicht konvertieren: %(error)s") % {"error": error_text[:300]})
    raise RuntimeError(_("LibreOffice konnte keine PDF-Datei erzeugen."))


def _convert_image(source_path, target):
    try:
        with Image.open(source_path) as image:
            validate_image_dimensions(image)
            image.seek(0)
            output_extension = "jpg" if target == "jpg" else target
            output_path = source_path.with_name(f"{source_path.stem}-converted.{output_extension}")

            if target == "jpg":
                image = image.convert("RGB")
                image.save(output_path, format="JPEG", quality=90, optimize=True)
            elif target == "png":
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA")
                image.save(output_path, format="PNG", optimize=True)
            elif target == "webp":
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA")
                image.save(output_path, format="WEBP", quality=86, method=6)
            elif target == "pdf":
                image = image.convert("RGB")
                image.save(output_path, format="PDF", resolution=100.0)
            else:
                raise RuntimeError(_("Dieses Zielformat wird für Bilder nicht unterstützt."))
    except Image.DecompressionBombError as exc:
        raise ConversionResourceLimitError(_("Die Bildabmessungen sind zu gross.")) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise RuntimeError(_("Das Bild konnte nicht gelesen oder konvertiert werden.")) from exc

    return output_path


def _converter_context(selected_target="pdf"):
    return {
        "max_upload_label": _format_file_size(MAX_CONVERTER_UPLOAD_SIZE),
        "selected_target": selected_target,
        "office_extensions": sorted(ext[1:].upper() for ext in OFFICE_TO_PDF_EXTENSIONS),
        "image_extensions": sorted(ext[1:].upper() for ext in IMAGE_EXTENSIONS),
    }


@login_required
@require_http_methods(["GET", "POST"])
def file_converter_view(request):
    if request.method == "GET":
        return render(request, "app/file_converter.html", _converter_context())

    uploaded_file = request.FILES.get("file")
    target = (request.POST.get("target") or "pdf").strip().lower()

    if target not in TARGET_CONTENT_TYPES:
        messages.error(request, _("Dieses Zielformat wird noch nicht unterstützt."))
        return render(request, "app/file_converter.html", _converter_context(target))

    if not uploaded_file:
        messages.error(request, _("Bitte wähle zuerst eine Datei aus."))
        return render(request, "app/file_converter.html", _converter_context(target))

    if uploaded_file.size > MAX_CONVERTER_UPLOAD_SIZE:
        messages.error(request, _("Die Datei ist zu groß. Maximal erlaubt sind %(size)s.") % {"size": _format_file_size(MAX_CONVERTER_UPLOAD_SIZE)})
        return render(request, "app/file_converter.html", _converter_context(target))

    safe_name = get_valid_filename(uploaded_file.name or "datei") or "datei"
    source_suffix = Path(safe_name).suffix.lower()

    if not source_suffix:
        messages.error(request, _("Die Datei braucht eine erkennbare Dateiendung."))
        return render(request, "app/file_converter.html", _converter_context(target))

    is_image = source_suffix in IMAGE_EXTENSIONS
    is_office = source_suffix in OFFICE_TO_PDF_EXTENSIONS

    if target != "pdf" and not is_image:
        messages.error(request, _("Dieses Zielformat ist aktuell nur für Bilder verfügbar."))
        return render(request, "app/file_converter.html", _converter_context(target))

    if target == "pdf" and not (is_image or is_office):
        messages.error(request, _("Diese Datei kann aktuell nicht zu PDF konvertiert werden."))
        return render(request, "app/file_converter.html", _converter_context(target))

    if is_image and target in IMAGE_TARGETS:
        converter = _convert_image
    elif target == "pdf" and is_office:
        converter = lambda path, chosen_target: _convert_office_to_pdf(path, path.parent)
    else:
        messages.error(request, _("Diese Kombination aus Datei und Zielformat wird nicht unterstützt."))
        return render(request, "app/file_converter.html", _converter_context(target))

    temp_dir = tempfile.TemporaryDirectory(prefix="mytools-converter-")
    source_path = Path(temp_dir.name) / safe_name
    try:
        _write_uploaded_file(uploaded_file, source_path)

        output_path = Path(converter(source_path, target))
        output_size = output_path.stat().st_size
        if output_size > MAX_CONVERTER_OUTPUT_SIZE:
            messages.error(
                request,
                _("Die konvertierte Datei ist zu gross. Maximal erlaubt sind %(size)s.") % {
                    "size": _format_file_size(MAX_CONVERTER_OUTPUT_SIZE),
                },
            )
            temp_dir.cleanup()
            return render(
                request,
                "app/file_converter.html",
                _converter_context(target),
                status=413,
            )
    except ConversionResourceLimitError as exc:
        temp_dir.cleanup()
        messages.error(request, str(exc))
        return render(
            request,
            "app/file_converter.html",
            _converter_context(target),
            status=413,
        )
    except (OSError, RuntimeError) as exc:
        temp_dir.cleanup()
        messages.error(request, str(exc))
        return render(request, "app/file_converter.html", _converter_context(target))

    original_stem = Path(safe_name).stem or "konvertiert"
    output_extension = "jpg" if target == "jpg" else target
    download_name = f"{original_stem}-konvertiert.{output_extension}"
    return _download_response(
        output_path,
        download_name,
        target,
        cleanup=temp_dir.cleanup,
    )
