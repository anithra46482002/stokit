"""Image upload for the React admin (multipart/form-data).

Files are stored under MEDIA_ROOT/uploads/<random>.<ext>. The returned `image_path` is the SAME
relative form the PHP admin stored (e.g. "uploads/ab12.webp"), so the Flutter-facing URLs built as
LEGACY_BASE_URL + image_path keep working. Existing files and database values are never touched.
"""
import uuid

from django.conf import settings
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import AdminRolePermission

MAX_BYTES = 5 * 1024 * 1024
SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".webp": (b"RIFF",),  # plus "WEBP" at offset 8, checked below
}


def _looks_like(ext, head):
    if not any(head.startswith(sig) for sig in SIGNATURES[ext]):
        return False
    return ext != ".webp" or head[8:12] == b"WEBP"


class ImageUploadView(APIView):
    required_resource = "catalogue"  # POST is limited to SUPER_ADMIN / ADMIN by AdminRolePermission
    permission_classes = [AdminRolePermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"file": "A file is required (multipart field 'file')."}, status=400)
        name = (upload.name or "").lower()
        ext = "." + name.rsplit(".", 1)[1] if "." in name else ""
        if ext not in SIGNATURES:
            return Response({"file": "Only JPG, PNG, GIF or WEBP images are accepted."}, status=400)
        if upload.size > MAX_BYTES:
            return Response({"file": "Image must be 5 MB or smaller."}, status=400)
        head = upload.read(16)
        upload.seek(0)
        if not _looks_like(ext, head):
            return Response({"file": "The file content does not match its image extension."}, status=400)

        if not getattr(settings, "SERVE_LOCAL_UPLOADS", False):
            return Response({"detail": "Local upload serving is disabled. Enable SERVE_LOCAL_UPLOADS for local/ngrok development or configure production media storage."}, status=503)
        folder = settings.MEDIA_ROOT / "uploads"
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}{ext}"
        with open(folder / filename, "xb") as handle:
            for chunk in upload.chunks():
                handle.write(chunk)
        image_path = f"uploads/{filename}"
        return Response({"image_path": image_path, "url": request.build_absolute_uri("/admin/manage/" + image_path) if getattr(settings, "SERVE_LOCAL_UPLOADS", False) else None}, status=201)
