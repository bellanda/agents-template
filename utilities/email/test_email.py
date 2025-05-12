import os

import dotenv
from smtp_client import SMTPClient

dotenv.load_dotenv()

if __name__ == "__main__":
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    email = os.getenv("SMTP_USERNAME")
    app_password = os.getenv("SMTP_PASSWORD")

    for variable in [smtp_server, smtp_port, email, app_password]:
        if variable is None:
            raise ValueError(f"Variável de ambiente não encontrada: {variable}")

    client = SMTPClient(smtp_server, smtp_port, email, app_password)

    client.send_email(
        **dict(
            to="gustavobellanda@hpeautos.com.br",
            cc="",
            subject="Veículos cripple pendentes há mais de 10 dias",
            email_content="""<h1>Teste</h1>
            <p>Teste</p>
            """,
            attachments=[r"\\fscatorg01\Fileserver\Share\Reports Qualidade\Cripple 10 dias Detalhados por Chassi.xlsx"],
        )
    )
