from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_seller = models.BooleanField(default=False)
    bio = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

    @classmethod
    def for_user(cls, user):
        """Ambil Profile user, dibuat kalau belum ada (user lama/superuser)."""
        profile, _ = cls.objects.get_or_create(user=user)
        return profile
