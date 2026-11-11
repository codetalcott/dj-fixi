"""The one model the pitfalls page needs: something a form can create."""

from django.db import models


class Note(models.Model):
    text = models.CharField(max_length=200)

    def __str__(self):
        return self.text
