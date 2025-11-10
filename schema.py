import marshmallow

from marshmallow import Schema
from marshmallow.fields import Boolean
from marshmallow.fields import DateTime
from marshmallow.fields import Field
from marshmallow.fields import Integer
from marshmallow.fields import List
from marshmallow.fields import Nested
from marshmallow.fields import String


class EmailAddressSchema(Schema):

    address = String()
    name = String()


class SenderSchema(Schema):

    email_address = Nested(EmailAddressSchema, data_key='emailAddress')


class RecipientSchema(Schema):

    email_address = Nested(EmailAddressSchema, data_key='emailAddress')


class BodySchema(Schema):

    content = String()
    content_type = String(data_key='contentType')


class Base64ContentField(Field):
    """
    A string (not bytes) of base64 encoded "bytes".
    https://learn.microsoft.com/en-us/graph/api/resources/fileattachment?view=graph-rest-1.0#properties
    See contentBytes
    """

    def _deserialize(self, string_of_bytes, attr, data, **kwargs):
        try:
            return base64.b64decode(string_of_bytes)
        except TypeError:
            raise ValidationError(
                'Base 64 content field must be string or bytes.')


class AttachmentSchema(Schema):

    content_type = String(data_key='contentType')
    content = Base64ContentField(data_key='contentBytes')
    id = String()
    is_inline = Boolean(data_key='isInline')
    last_modified_datetime = DateTime(data_key='lastModifiedDateTime')
    name = String()
    size = Integer()

    @marshmallow.post_load
    def make_expected(self, data, **kwargs):
        class Payload:

            def __init__(self, content):
                self.payload = content


        expected = Payload(data['content'])
        return expected


class GraphMessageSchema(Schema):

    sender = Nested(EmailAddressSchema)
    toRecipients = Nested(RecipientSchema, many=True)
    subject = String()
    received_datetime = DateTime(data_key='receivedDateTime')
    body = Nested(BodySchema)

    attachments = List(
        Nested(AttachmentSchema)
    )

