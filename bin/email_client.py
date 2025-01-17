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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os import environ
from smtplib import SMTP, SMTP_SSL

import mistune
from jinja_utils import Jinja
from logging_utils import get_logger


class Email:
    """Email class that wraps the logic of writing HTML emails that will be
    sent to one or multiple recipients. The class exposes all of its attributes
    and expects a dictionary at `message` parameter for rendering the Jinja
    template. Finally, `send` delives the email and finishes.

    Args:
        host (str, optional): SMTP host to connect to
        port (int, optional): SMTP port used when connecting
        user (str, optional): SMTP user used during authentication
        password (str, optional): SMTP password used during authentication
        tls (bool, optional): whether to use TLS connections instead of STARTTLS
        from_addrs (str, optional): sender address
        to_addrs (str, optional): recipient(s) address(es)
        subject (str, optional): mail subject
    """

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
    def message(self) -> str:
        """Gets the generated multipart message which will be the body of the email

        Returns:
            str: the email's body
        """
        return self._message

    @message.setter
    def message(self, obj: dict[str, object]):
        """Sets the dictionary that defines the body of the email and generates
        the associated template.

        Args:
            obj (dict[str, object]): template's base dictionary
        """
        multipart_msg = MIMEMultipart("alternative")

        # set message data
        multipart_msg["Subject"] = self.subject
        multipart_msg["From"] = self.from_addrs
        # recipients must be an string, not list
        multipart_msg["To"] = ", ".join(self.recipients)

        msg = self.jinja.render(r"body.jinja", obj)
        markdown = mistune.Markdown()
        md_message = markdown(msg)

        html = self.jinja.render(r"email.jinja", {"email_body": md_message})

        plain_part = MIMEText(msg, "plain")
        html_part = MIMEText(html, "html")

        multipart_msg.attach(plain_part)
        multipart_msg.attach(html_part)

        self._message = multipart_msg.as_string()

    def send(self):
        """Sends the email to the given recipients iff all required parameters
        are defined, that is: SMTP host, port, sender address, recipient(s)
        address(es) and subject.
        """
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
            except Exception as exc:
                self.log.exception("Failed to send SMTP email!", exc_info=exc)
            finally:
                if smtp is not None:
                    smtp.quit()
        else:
            self.log.warning(
                "Missing required attributes for sending an email. Email not sent"
            )
