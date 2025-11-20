import sqlalchemy as sa

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):

    message_id = Column(
        String,
        comment = 'Graph client message id that created or updated this record.'
    )

    attachment_name = Column(
        String,
        comment = 'Name from Graph message for the HTML attachment this data was scraped from.'
    )

    @classmethod
    def one_or_none_from_data(cls, session, data):
        """
        One instance or None for primary key from data scraped from the HTML
        attachment.
        """
        query = sa.select(cls).where(
            cls.registration == data['registration'],
            cls.wqar_serial == data['wqar_serial'],
        )
        return session.scalars(query).one_or_none()

    @classmethod
    def instance_for_message_attachment(cls, session, message, attachment):
        """
        Return instance if the message id and attachment already exist. Use
        this method to avoid scraping attachments from the mailbox.
        """
        query = sa.select(cls).where(
            cls.message_id == message['id'],
            cls.attachment_name == attachment['name'],
        )
        return session.scalars(query).one_or_none()

    @classmethod
    def new_from_data(cls, data, message, attachment):
        """
        New instance from message, attachment and data scraped from it.
        """
        instance = cls(**data)
        instance.message_id = message['id']
        instance.attachment_name = attachment['name']
        return instance

    def update_from_data(self, data, message, attachment):
        """
        Update this instance from data parsed from a message's attachment.
        """
        for key, value in data.items():
            setattr(self, key, value)
        self.message_id = message['id']
        self.attachment_name = attachment['name']


class WGLDownloadReport(Base):

    __tablename__ = 'wgl_download_report'

    registration = Column(
        String(),
        primary_key = True,
    )

    wqar_serial = Column(
        String(),
        primary_key = True,
    )

    last_download_complete_at = Column(DateTime(timezone=True))

    last_download_file = Column(String())

    last_download_file_size = Column(String())

    last_activity = Column(DateTime(timezone=True))

    successful_downloads = Column(Integer)

    unsuccessful_downloads = Column(Integer)


class WGLDataLoading(Base):

    __tablename__ = 'wgl_data_loading'

    registration = Column(
        String(),
        primary_key = True,
    )

    wqar_serial = Column(
        String(),
        primary_key = True,
    )

    last_complete_eadl_status_file_download_at = Column(
        DateTime(timezone=True)
    )

    last_complete_eadl_event_log_file_download_at = Column(
        DateTime(timezone=True),
    )

    last_complete_ptman_file_upload_at = Column(
        DateTime(timezone=True),
    )

    last_complete_lsp_upload_at = Column(
        DateTime(timezone=True),
    )

    successful_uploads_ptman = Column(Integer)

    successful_uploads_lsp = Column(Integer)

