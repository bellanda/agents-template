import mimetypes
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import encode_rfc2231

import dotenv

dotenv.load_dotenv()


class SMTPClient:
    """
    A class to send emails using an SMTP server.
    """

    def __init__(self, smtp_server: str, smtp_port: int, email: str, app_password: str) -> None:
        """
        Initializes the SMTP client and authenticates with the server.

        Args:
            smtp_server (str): The address of the SMTP server.
            smtp_port (int): The port number to use for the SMTP server.
            email (str): The email address of the sender.
            app_password (str): The app-specific password for the email account.
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email = email

        # Connect to the SMTP server and start TLS for security
        self.server = smtplib.SMTP(smtp_server, smtp_port)
        self.server.starttls()  # Start TLS for security
        self.server.login(email, app_password)  # Log in to the server

    def send_email(
        self, to: str, subject: str, email_content: str, cc: str = None, bcc: str = None, attachments: list = None
    ) -> None:
        """
        Sends an email with the specified content and optional attachments.

        Args:
            to (str): The recipient's email address.
            subject (str): The subject of the email.
            email_content (str): The body content of the email.
            cc (str, optional): A comma-separated string of CC (carbon copy) email addresses. Defaults to None.
            bcc (str, optional): A comma-separated string of BCC (blind carbon copy) email addresses. Defaults to None.
            attachments (list, optional): List of file paths to attach to the email. Defaults to None.
        """
        # Create the email content
        msg = MIMEMultipart()
        msg["From"] = self.email
        msg["To"] = to
        if cc is not None:
            msg["Cc"] = cc
        if bcc is not None:
            msg["Bcc"] = bcc
        msg["Subject"] = subject
        msg.attach(MIMEText(email_content, "html"))

        # Handle attachments
        if attachments:
            for attachment_path in attachments:
                # Verifica se o arquivo existe
                if os.path.isfile(attachment_path):
                    # Adivinha o tipo MIME do arquivo
                    mime_type, _ = mimetypes.guess_type(attachment_path)
                    if mime_type is None:
                        mime_type = "application/octet-stream"  # Tipo padrão se não for reconhecido

                    # Separa o tipo e sub-tipo MIME
                    mime_main, mime_sub = mime_type.split("/", 1)

                    # Abre o arquivo em modo binário
                    with open(attachment_path, "rb") as attachment_file:
                        # Cria um objeto MIME correspondente
                        part = MIMEBase(mime_main, mime_sub)
                        part.set_payload(attachment_file.read())
                        # Codifica o payload em base64
                        encoders.encode_base64(part)
                        # Obtém o nome do arquivo
                        filename = os.path.basename(attachment_path)
                        # Codifica o nome do arquivo para lidar com caracteres especiais
                        _filename_encoded = encode_rfc2231(filename, "utf-8")
                        # Adiciona os headers apropriados
                        part.add_header("Content-Disposition", "attachment", filename=filename)
                        part.add_header("Content-Type", mime_type, name=filename)
                        # Anexa o objeto MIME à mensagem
                        msg.attach(part)
                else:
                    print(f"Arquivo não encontrado: {attachment_path}")

        # Prepare a list of all recipients
        all_receivers = to.split(";")
        if cc:
            all_receivers += cc.split(",")
        if bcc:
            all_receivers += bcc.split(",")

        # Send the email
        self.server.sendmail(self.email, all_receivers, msg.as_string())


smtp_server = os.getenv("SMTP_SERVER")
smtp_port = os.getenv("SMTP_PORT")
email = os.getenv("SMTP_USERNAME")
app_password = os.getenv("SMTP_PASSWORD")

for variable in [smtp_server, smtp_port, email, app_password]:
    if variable is None:
        raise ValueError(f"Variável de ambiente não encontrada: {variable}")

client = SMTPClient(smtp_server, smtp_port, email, app_password)
