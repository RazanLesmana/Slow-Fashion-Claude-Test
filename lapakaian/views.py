from django.shortcuts import render


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)


def coming_soon(request, title="Segera hadir", **kwargs):
    """Halaman sementara untuk URL modul yang belum selesai dikerjakan."""
    return render(request, "coming_soon.html", {"title": title})
