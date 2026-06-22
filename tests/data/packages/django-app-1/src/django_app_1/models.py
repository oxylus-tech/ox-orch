from django.db import models


__all__ = ("Person", "Organisation")


class Person(models.Model):
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)


class Organisation(models.Model):
    name = models.CharField(max_length=64)
