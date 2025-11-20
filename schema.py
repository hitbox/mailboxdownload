import logging

from datetime import datetime
from datetime import timezone

import marshmallow

from marshmallow import Schema
from marshmallow import post_load
from marshmallow.fields import Boolean
from marshmallow.fields import DateTime
from marshmallow.fields import Field
from marshmallow.fields import Integer
from marshmallow.fields import List
from marshmallow.fields import Nested
from marshmallow.fields import String

logger = logging.getLogger(__name__)

class SafeDateTime(Field):

    def __init__(self, fmt, timezone=False, **kwargs):
        self.fmt = fmt
        self.timezone = timezone
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        if not value:
            return None
        try:
            result = datetime.strptime(value, self.fmt)
            if self.timezone:
                result = result.replace(tzinfo=self.timezone)
            return result
        except (ValueError, TypeError):
            logger.debug('failed %s with %s', value, self.fmt)


class SeparatedInteger(Field):

    def __init__(self, separator, index, **kwargs):
        super().__init__(**kwargs)
        self.separator = separator
        self.index = index

    def _deserialize(self, value, attr, data, **kwargs):
        if not value:
            return None
        values = value.split(self.separator)
        return int(values[self.index])


WGL_DATETIME_FORMAT = '%a, %b %d, %Y %H:%M:%S'

class WGLAircraftDownloadReportSchema(Schema):

    registration = String(data_key='Registration')

    wqar_serial = String(data_key='WQAR Serial Number')

    last_download_complete_at = SafeDateTime(
        fmt = WGL_DATETIME_FORMAT,
        data_key = 'Last complete download at',
        timezone = timezone.utc,
    )

    last_download_file = String(data_key='Last download file')

    last_download_file_size = String(
        data_key = 'Last downloaded file size',
    )

    last_activity = SafeDateTime(
        fmt = WGL_DATETIME_FORMAT,
        data_key = 'Last activity',
        timezone = timezone.utc,
    )

    hours_since_last_complete_download = String(
        data_key = 'Hours since last complete download',
    )

    successful_downloads = Integer(data_key='Successful downloads')

    unsuccessful_downloads = Integer(data_key='Unsuccessful downloads')

    @post_load
    def remove_hours_since_last_complete_download(self, data, **kwargs):
        data.pop('hours_since_last_complete_download', None)
        return data


class WGLDataLoadingSchema(Schema):

    registration = String(data_key='Registration')

    wqar_serial = String(data_key='WQAR Serial Number')

    last_complete_eadl_status_file_download_at = SafeDateTime(
        fmt = WGL_DATETIME_FORMAT,
        data_key = 'Last completed eADL STATUS file download at',
        timezone = timezone.utc,
    )

    last_complete_eadl_event_log_file_download_at = SafeDateTime(
        fmt = WGL_DATETIME_FORMAT,
        data_key = 'Last completed eADL EVENT LOG file download at',
        timezone = timezone.utc,
    )

    last_complete_ptman_file_upload_at = SafeDateTime(
        fmt = WGL_DATETIME_FORMAT,
        data_key = 'Last completed PTMAN file upload at',
        timezone = timezone.utc,
    )

    last_complete_lsp_upload_at = SafeDateTime(
        fmt = WGL_DATETIME_FORMAT,
        data_key = 'Last completed LSP upload at',
        timezone = timezone.utc,
    )

    successful_uploads_ptman_lsp = String(
        data_key = 'Successful uploads (PTMAN/LSP)',
    )

    @post_load
    def split_successful_uploads(self, data, **kwargs):
        combined = data.pop('successful_uploads_ptman_lsp', None)
        if combined:
            lsp, ptman = map(int, combined.split('/'))
            data['successful_uploads_ptman'] = ptman
            data['successful_uploads_lsp'] = lsp
        return data
