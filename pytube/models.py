#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
from time import clock

# AWS libraries
import boto
from s3file import s3open

try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen


class Video(object):
    """Class representation of a single instance of a YouTube video.
    """
    def __init__(self, url, filename, extension, resolution=None,
                 video_codec=None, profile=None, video_bitrate=None,
                 audio_codec=None, audio_bitrate=None):
        """Sets-up the video object.

        :param str url:
            The url of the video. (e.g.: https://youtube.com/watch?v=...)
        :param str filename:
            The filename (minus the extention) to save the video.
        :param str extention:
            The desired file extention (e.g.: mp4, flv, webm).
        :param str resolution:
            *Optional* The broadcasting standard (e.g.: 720p, 1080p).
        :param str video_codec:
            *Optional* The codec used to encode the video.
        :param str profile:
            *Optional* The arbitrary quality profile.
        :param str video_bitrate:
            *Optional* The bitrate of the video over sampling interval.
        :param str audio_codec:
            *Optional* The codec used to encode the audio.
        :param str audio_bitrate:
            *Optional* The bitrate of the video's audio over sampling interval.
        """
        self.url = url
        self.filename = filename
        self.extension = extension
        self.resolution = resolution
        self.video_codec = video_codec
        self.profile = profile
        self.video_bitrate = video_bitrate
        self.audio_codec = audio_codec
        self.audio_bitrate = audio_bitrate

    def download(self, path, chunk_size=8 * 1024, on_progress=None,
                 on_finish=None, force_overwrite=False):
        """Downloads the video.

        :param str path:
            The destination output directory.
        :param int chunk_size:
            File size (in bytes) to write to buffer at a time. By default,
            this is set to 8 bytes.
        :param func on_progress:
            *Optional* function to be called every time the buffer is written
            to. Arguments passed are the bytes recieved, file size, and start
            datetime.
        :param func on_finish:
            *Optional* callback function when download is complete. Arguments
            passed are the full path to downloaded the file.
        :param bool force_overwrite:
            *Optional* force a file overwrite if conflicting one exists.
        """
        path = os.path.normpath(path)
        if os.path.isdir(path):
            filename = "{0}.{1}".format(self.filename, self.extension)
            path = os.path.join(path, filename)
        # TODO: If it's not a path, this should raise an ``OSError``.
        # TODO: Move this into cli, this kind of logic probably shouldn't be
        # handled by the library.
        if os.path.isfile(path) and not force_overwrite:
            raise OSError("Conflicting filename:'{0}'".format(self.filename))
        # TODO: Split up the downloading and OS jazz into separate functions.
        response = urlopen(self.url)
        meta_data = dict(response.info().items())
        file_size = int(meta_data.get("Content-Length") or
                        meta_data.get("content-length"))
        self._bytes_received = 0
        start = clock()
        # TODO: Let's get rid of this whole try/except block, let ``OSErrors``
        # fail loudly.
        try:
            with open(path, 'wb') as dst_file:
                while True:
                    self._buffer = response.read(chunk_size)
                    # Check if the buffer is empty (aka no bytes remaining).
                    if not self._buffer:
                        if on_finish:
                            # TODO: We possibly want to flush the
                            # `_bytes_recieved`` buffer before we call
                            # ``on_finish()``.
                            on_finish(path)
                        break

                    self._bytes_received += len(self._buffer)
                    dst_file.write(self._buffer)
                    if on_progress:
                        on_progress(self._bytes_received, file_size, start)

        except KeyboardInterrupt:
            # TODO: Move this into the cli, ``KeyboardInterrupt`` handling
            # should be taken care of by the client. Also you should be allowed
            # to disable this.
            os.remove(path)
            raise KeyboardInterrupt(
                "Interrupt signal given. Deleting incomplete video.")

    def download_s3(self, s3_bucket_name, aws_key, aws_secret,
                    video_dir='', chunk_size=8 * 1024, on_progress=None,
                    on_finish=None, acl_permission='public-read'):
        """
        Downloads video to S3

        :param str s3_bucket_name:
            S3 bucket name with output directory
        :param str aws_key:
            AWS Key id for the account
        :param str aws_secret:
            AWS Secret Key for the account
        :param str video_dir:
            video directory to store the file within the bucket
        :param int chunk_size:
            File size (in bytes) to write to buffer at a time. By default,
            this is set to 8 bytes.
        :param func on_progress:
            *Optional* function to be called every time the buffer is written
            to. Arguments passed are the bytes recieved, file size, and start
            datetime.
        :param func on_finish:
            *Optional* callback function when download is complete. Arguments
            passed are the full path to downloaded the file.
        :param str acl_permission:
            *Optional* set the acl permissions for the new key saved to s3.
        :return: tuple of s3_bucket_name, video_key_path
        """
        # Setup AWS S3 connections
        s3_connection = boto.connect_s3(aws_access_key_id=aws_key,
                                        aws_secret_access_key=aws_secret)
        # TODO: Create bucket if it doesn't exist
        video_key_path = "{0}.{1}".format(self.filename, self.extension)
        if video_dir:
            video_key_path = os.path.join(video_dir, video_key_path)
        try:
            video_key = s3_connection.get_bucket(s3_bucket_name).new_key(video_key_path)
        except:
            print "S3 bucket does not exist. Cannot save file to S3"
            return None, None

        # Download the video
        response = urlopen(self.url)
        meta_data = dict(response.info().items())
        file_size = int(meta_data.get("Content-Length") or
                        meta_data.get("content-length"))
        self._bytes_received = 0
        start = clock()

        try:
            with s3open(video_key.generate_url(60), key=aws_key, secret=aws_secret,
                        create=False) as dst_file:
                while True:
                    self._buffer = response.read(chunk_size)
                    # Check if the buffer is empty (aka no bytes remaining).
                    if not self._buffer:
                        if on_finish:
                            # TODO: We possibly want to flush the
                            # `_bytes_recieved`` buffer before we call
                            # ``on_finish()``.
                            # on_finish(path)
                            pass
                        break

                    self._bytes_received += len(self._buffer)
                    dst_file.write(self._buffer)
                    if on_progress:
                        on_progress(self._bytes_received, file_size, start)
            # Set key permissions to public read after download
            video_key.set_acl(acl_permission)
            return s3_bucket_name, video_key_path

        except KeyboardInterrupt:
            # TODO: Move this into the cli, ``KeyboardInterrupt`` handling
            # should be taken care of by the client. Also you should be allowed
            # to disable this.
            video_key.delete()
            raise KeyboardInterrupt(
                "Interrupt signal given. Deleting incomplete video.")

    def __repr__(self):
        """A clean representation of the class instance."""
        return "<Video: {0} (.{1}) - {2} - {3}>".format(
            self.video_codec, self.extension, self.resolution, self.profile)

    def __lt__(self, other):
        """The "less than" (lt) method is used for comparing video object to
        one another. This useful when sorting.

        :param other:
            The instance of the other video instance for comparison.
        """
        if isinstance(other, Video):
            v1 = "{0} {1}".format(self.extension, self.resolution)
            v2 = "{0} {1}".format(other.extension, other.resolution)
            return (v1 > v2) - (v1 < v2) < 0
