from django.db import models
from django.contrib.auth.models import User


__all__ = ("Person", "Organisation")


class Person(models.Model):
    user = models.ForeignKey(User, models.SET_NULL, null=True, blank=True)
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)


class Organisation(models.Model):
    name = models.CharField(max_length=64)
