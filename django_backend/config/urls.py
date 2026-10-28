from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import include, path, re_path
from django.http import FileResponse, Http404
from pathlib import Path
import mimetypes

def serve_local_upload(request, path):
    """Serve only explicitly enabled files under MEDIA_ROOT/uploads, independent of DEBUG."""
    if not getattr(settings, "SERVE_LOCAL_UPLOADS", False):
        raise Http404
    media_root = Path(settings.MEDIA_ROOT).resolve()
    requested = (media_root / path).resolve()
    try:
        requested.relative_to(media_root / "uploads")
    except ValueError:
        raise Http404
    if not requested.is_file():
        raise Http404
    content_type, _ = mimetypes.guess_type(str(requested))
    response = FileResponse(requested.open("rb"), content_type=content_type or "application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    return response

urlpatterns = [
    path("api/", include("legacy_api.urls")),      # Flutter contract (unchanged paths)
    path("admin-api/", include("adminapi.urls")),  # React admin (separate namespace)
]

if settings.ADMIN_FRONTEND_URL:
    # Django Admin is not installed; /admin used to 404. Point it at the React admin instead.
    def admin_redirect(request):
        return HttpResponseRedirect(settings.ADMIN_FRONTEND_URL)

    urlpatterns += [re_path(r"^admin/?$", admin_redirect, name="admin-frontend-redirect")]

# Always registered; serve_local_upload enforces the SERVE_LOCAL_UPLOADS opt-in per request (404 when
# disabled). A conditional import-time registration let a long-lived server started before the
# route/setting existed silently 404 every image. DEBUG must not implicitly expose uploaded media.
urlpatterns += [re_path(r"^admin/manage/(?P<path>uploads/.*)$", serve_local_upload, name="local-upload-media")]