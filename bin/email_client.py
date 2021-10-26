#                                Email
#                  Copyright (C) 2021 - Javinator9889
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#                   (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#               GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Email service wrapped at :class:`Email` class"""
from os import environ
from smtplib import SMTP, SMTP_SSL
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mistune
from jinja_utils import Jinja
from md import HighlightRenderer

from logging_utils import get_logger


class Email:
    def __init__(
        self,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        tls: bool = None,
        from_addrs: str = None,
        to_addrs: str = None,
        subject: str = None,
    ):
        self.smtp_host = host or environ.get("SMTP_HOST")
        self.smtp_port = port or environ.get("SMTP_PORT")
        self.smtp_user = user or environ.get("SMTP_USER")
        self.smtp_pass = password or environ.get("SMTP_PASS", "")
        self.smtp_tls = tls or environ.get("SMTP_TLS", "").lower() in {"1", "true"}
        self.from_addrs = from_addrs or environ.get("EMAIL_FROM")
        to_addrs = to_addrs or environ.get("EMAIL_TO")
        # if we have commas at "to" then multiple recipients are defined
        # "sendmail" accepts a list as "to" parameter, so split the variable
        # and send it. Just to be careful, delete any whitespace present at
        # destination email addresses
        self.recipients = (
            to_addrs.replace(" ", "").split(",") if to_addrs is not None else None
        )
        self.subject = subject or environ.get("EMAIL_SUBJECT")
        self.log = get_logger()
        self.jinja = Jinja()

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, obj: dict[str, object]):
        multipart_msg = MIMEMultipart("alternative")

        # set message data
        multipart_msg["Subject"] = self.subject
        multipart_msg["From"] = self.from_addrs
        multipart_msg["To"] = self.recipients

        msg = self.jinja.render(r"body.jinja", obj)
        markdown = mistune.Markdown(renderer=HighlightRenderer())
        md_message = markdown(msg)

        html = self.jinja.render(r"email.jinja", {"email_body": md_message})

        plain_part = MIMEText(msg, "plain")
        html_part = MIMEText(html, "html")

        multipart_msg.attach(plain_part)
        multipart_msg.attach(html_part)

        self._message = multipart_msg.as_string()

    def send(self):
        if all(
            (
                self.smtp_host,
                self.smtp_port,
                self.from_addrs,
                self.recipients,
                self.subject,
            )
        ):
            smtp = None
            try:
                _Class = SMTP_SSL if self.smtp_tls else SMTP
                smtp = _Class(self.smtp_host, self.smtp_port)
                if self.smtp_user is not None:
                    self.log.info("Logging in into SMTP server")
                    smtp.ehlo()
                    if smtp.has_extn("STARTTLS"):
                        self.log.info("SMTP server supports TLS encryption")
                        smtp.starttls()
                        smtp.ehlo()  # re-identify ourselves over TLS connection
                    smtp.login(self.smtp_user, self.smtp_pass)

                smtp.sendmail(self.from_addrs, self.recipients, self.message)
            except Exception as e:
                self.log.exception("Failed to send SMTP email!", exc_info=e)
            finally:
                if smtp is not None:
                    smtp.quit()
        else:
            self.log.warning(
                "Missing required attributes for sending an email. Email not sent"
            )
