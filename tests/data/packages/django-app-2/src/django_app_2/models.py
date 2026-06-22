from django.db import models

from django_app_1.models import Person


__all__ = ("PersonAddress",)


class PersonAddress(models.Model):
    person = models.ForeignKey(Person, models.CASCADE)
