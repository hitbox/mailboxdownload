# mailboxdownload

Python 3+ parse WGL reports in html attachments from emails and upsert to database.

## NOTES

The specifics for each scrape run are so full of specifics and sensitive information, I'm keeping them in scripts in the instance directory. They will just have to be passed around behind the version control.

## mailboxdownload.py

Provides classes and functions to iterate and download attachments.

## model.py
    
Database models for two WGL reports expected in the attachments.

## parse.py

Parse HTML tables into a dict.

## schema.py

Two deserializing schemas for the reports.
