#!/usr/bin/env python

from __future__ import unicode_literals

from lms.djangoapps.certificates.models import GeneratedCertificate


def convert_download_url():
    certs = GeneratedCertificate.objects.exclude(download_url='')
    for cert in certs:
        url = cert.download_url
        cert.download_url = url.replace("http://localhost:18090", "")
        cert.save()