from abc import ABCMeta, abstractmethod

from django.conf import settings
import gridfs
from gridfs.errors import NoFile
import logging
from PIL import Image
from StringIO import StringIO

from django.core.validators import ValidationError

from openedx.core.djangoapps.content.course_overviews.models import CourseOverviewImageConfig
from xmodule.exceptions import NotFoundError


class _MongoDBDfs(object):
    """MongoDB based Distributed files System.
    """
    __metaclass__ = ABCMeta

    def __init__(self, db_connection, bucket_name):
        """Constructor of DFS class.

            @param db_connection:   MongoDB database connection
            @type db_connection:    pymongo.database.Database/pymongo.MongoClient
            @param bucket_name:     collections' prefix names
            @type bucket_name:      string
        """
        self._fs = gridfs.GridFS(db_connection, bucket_name)
        self._fs_files = db_connection[bucket_name + ".files"]
        self._chunks = db_connection[bucket_name + ".chunks"]

    def _create_file(self, file_key, file_name, file_data, **kwargs):
        """Create a new file in MongoDB. Don't support database lock. But we could have one.
        """
        with self._fs.new_file(
            _id=file_key,
            filename=unicode(file_name),
            **kwargs
        ) as fp:
            if hasattr(file_data, '__iter__'):
                for chunk in file_data:
                    fp.write(chunk)
            else:
                fp.write(file_data)

            return '/' + file_key \
                if '/' != file_key[0] else file_key

    def delete_file(self, file_key):
        """Delete an file/image

            @param file_key:        primary key of file/image collection(DFS)
            @type file_key:         string
        """
        self._fs.delete(file_key)

    @abstractmethod
    def get_data_by_key(self, key):
        """Read data block by key"""
        raise NotImplementedError

    @abstractmethod
    def upload_file(self, file):
        """Upload file into MongoDB Dfs"""
        raise NotImplementedError


class ProgramCardImageDfs(_MongoDBDfs):
    """Program card image in Dfs"""
    class _CardImage(object):
        """Program card image data holder"""
        STREAM_DATA_CHUNK_SIZE = 1024

        def __init__(self, file_key, dfs_handle):
            """Constructor

                @param file_key:        image file key for MongoDB(unique)
                @type file_key:         string
                @param dfs_handle:      distributed file system handle
                @type dfs_handle:       GridFS
            """
            self._file_key = file_key
            self._dfs_handle = dfs_handle
            self._dfs_fp = self._dfs_handle.get(self._file_key)

        def __iter__(self):
            """Read file/image from MongoDB.
            """
            while True:
                chunk = self._dfs_fp.read(self.STREAM_DATA_CHUNK_SIZE)
                if len(chunk) == 0:
                    break
                yield chunk

        @property
        def length(self):
            """Return file length"""
            return self._dfs_fp.length

        @property
        def chunk_size(self):
            """Return file chunk size"""
            return self._dfs_fp.chunk_size

        @property
        def content_type(self):
            """Return image type"""
            return self._dfs_fp.image_type

    @classmethod
    def image_is_too_large(cls, memory_uploaded_image):
        """
            @param memory_uploaded_image:    upload image handle
            @type memory_uploaded_image:     django.core.files.uploadedfile.InMemoryUploadedFile
            @return:                         True: too large
            @rtype:                          boolean
        """
        return memory_uploaded_image.size > \
               settings.MAX_ASSET_UPLOAD_FILE_SIZE_IN_MB * 1000 ** 2

    def save_thumbnail_image(self, file_key, file_name, image_data, image_type, tempfile_path=None, dimensions=None):
        """Create a thumbnail for a given image.

            @param file_key:        image file key for MongoDB(unique)
            @type file_key:         string
            @param file_name:       file name
            @type file_name:        string
            @param image_data:      image binary data(type: `chunked data` Or `binary stream`)
            @type image_data:       binary Or list
            @param image_type:      image type
            @type image_type:       string
            @param tempfile_path:   temp image file path
            @type tempfile_path:    string
            @param dimensions:      optional param that represents (width, height) in pixels. It defaults to None.
            @type dimensions:       tuple Or None
            @return:                True: too large
            @rtype:                 Returns a tuple of (StaticContent, AssetKey)

            Reference method: `content.py :: def generate_thumbnail(self, content, tempfile_path=None, dimensions=None):`
        """
        if r'image/svg+xml' == image_type:
            # for svg simply store the provided svg file, since vector graphics should be good enough
            # for downscaling client-side
            if tempfile_path is None:
                thumbnail_file = StringIO(image_data)
            else:
                with open(tempfile_path) as f:
                    thumbnail_file = StringIO(f.read())

            return self._create_file(
                file_key, file_name, thumbnail_file, image_type=image_type
            )

        elif image_type is not None and image_type.split('/')[0] == 'image':
            # use PIL to do the thumbnail generation (http://www.pythonware.com/products/pil/)
            # My understanding is that PIL will maintain aspect ratios while restricting
            # the max-height/width to be whatever you pass in as 'size'
            # @todo: move the thumbnail size to a configuration setting?!?
            if tempfile_path is None:
                source = StringIO(image_data)
            else:
                source = tempfile_path

            # We use the context manager here to avoid leaking the inner file descriptor
            # of the Image object -- this way it gets closed after we're done with using it.
            thumbnail_file = StringIO()
            with Image.open(source) as image:
                # I've seen some exceptions from the PIL library when trying to save palletted
                # PNG files to JPEG. Per the google-universe, they suggest converting to RGB first.
                thumbnail_image = image.convert('RGB')

                if not dimensions:
                    dimensions = (128, 128)

                thumbnail_image.thumbnail(dimensions, Image.ANTIALIAS)
                thumbnail_image.save(thumbnail_file, 'JPEG')
                thumbnail_file.seek(0)

            # store this thumbnail as any other piece of content
            return self._create_file(
                file_key, file_name, thumbnail_file, image_type='image/jpeg'
            )

    def upload_file(self, file, file_key):
        """Save file/image into MongoDb.

            @param file:            upload image handle
            @type file:             django.core.files.uploadedfile.InMemoryUploadedFile
            @param file_key:        image file key for MongoDB(unique)
            @type file_key:         string
            @return:                file key
            @rtype:                 string
        """
        config = CourseOverviewImageConfig.current()
        if not config:
            raise ValidationError(
                r'Invalid image size configuration in `admin / site configuration`'
            )

        if self.image_is_too_large(file):
            raise ValidationError(
                r'The uploading file is too large: {}'.format(file.name)
            )

        return self.save_thumbnail_image(
            image_data=file.chunks() if file.multiple_chunks() else file.read(),
            image_type=file.content_type,
            file_key=file_key,
            file_name=file.name,
            tempfile_path=file.temporary_file_path() if file.multiple_chunks() else None,
            dimensions=config.large
        )

    def get_data_by_key(self, file_key):
        """Read file/image from MongoDB.

            @param file_key:        image file key for MongoDB(unique)
            @type file_key:         string
            @return:                Return program card image binary data holder
            @rtype:                 _CardImage
        """
        return ProgramCardImageDfs._CardImage(
            file_key, self._fs
        )

    def rename_image_file_key(self, last_file_key, new_file_key):
        """Rename image name(Change Doc. primary key)

            @param last_file_key:       old image file key for MongoDB(unique)
            @type last_file_key:        string
            @param new_file_key:        new image file key for MongoDB(unique)
            @type new_file_key:         string
            @return:                    Return new program card image doc. key in MongoDb.
            @rtype:                     string

        """
        if not last_file_key or not new_file_key:
            raise ValidationError(r'Invalid arguments for program card image renaming.')

        file_doc = self._fs_files.find_one({'_id': last_file_key})
        if not file_doc:
            raise NotFoundError(
                r'file doc primary key ({}) does not exist.'.format(last_file_key)
            )

        file_data = self._fs.get(last_file_key)
        new_file_key = self._fs.put(
            _id=new_file_key,
            image_type=file_doc.get('image_type'),
            filename=file_doc.get('filename'),
            data=file_data
        )

        if not new_file_key:
            raise NotFoundError(
                r'Cannot create new program card image by _ids : {} / {}'.format(last_file_key, new_file_key)
            )

        self.delete_file(last_file_key)

        return new_file_key
