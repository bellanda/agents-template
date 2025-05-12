import logging
import os
import pathlib
import time

import dotenv
import oracledb
from sqlalchemy import create_engine, event

# Configuração do Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Carregar variáveis de ambiente
try:
    dotenv_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if dotenv_path.exists():
        dotenv.load_dotenv(dotenv_path=dotenv_path)
        logging.info(f"Variáveis de ambiente carregadas de: {dotenv_path}")
    else:
        dotenv.load_dotenv()
        logging.info("Tentando carregar variáveis de ambiente do diretório atual ou padrão.")
except Exception as e:
    logging.warning(f"Não foi possível carregar o arquivo .env: {e}")

# Obter variáveis de ambiente
USERNAME = os.getenv("ORACLE_USERNAME")
PASSWORD = os.getenv("ORACLE_PASSWORD")
HOST = os.getenv("ORACLE_HOST")
PORT = os.getenv("ORACLE_PORT")
SERVICE_NAME = os.getenv("ORACLE_SERVICE_NAME")
CLIENT_PATH = os.getenv("CLIENT_PATH")
ENABLE_SQL_ALCHEMY_LOG = os.getenv("ORACLE_ENABLE_SQL_ALCHEMY_LOG", "false").lower() == "true"
ENABLE_ORACLE_TRACE_ENV = os.getenv("ORACLE_ENABLE_TRACE", "false").lower() == "true"

# Validação das credenciais
if None in [USERNAME, PASSWORD, HOST, PORT, SERVICE_NAME]:
    logging.error(
        "Variáveis de ambiente Oracle cruciais não foram encontradas: username, password, host, port, service_name"
    )
    raise ValueError("Variáveis de ambiente Oracle cruciais não encontradas")

# Inicialização do Cliente Oracle (opcional, mas recomendado se CLIENT_PATH for fornecido)
if CLIENT_PATH:
    try:
        os.environ["LD_LIBRARY_PATH"] = CLIENT_PATH
        oracledb.init_oracle_client(lib_dir=CLIENT_PATH)
        logging.info(f"Oracle Client inicializado a partir de: {CLIENT_PATH}")
    except Exception as e:
        # Decide se o erro é crítico ou apenas um aviso
        logging.warning(
            f"Falha ao inicializar Oracle Client em {CLIENT_PATH}: {e}. Tentando continuar (pode usar modo Thin)."
        )
        raise
else:
    logging.info(
        "CLIENT_PATH não definido. O driver oracledb tentará usar o modo Thin ou buscar o client no path do sistema."
    )


# Esta função só será chamada se o listener for registrado no engine
def enable_oracle_trace_listener(dbapi_connection, connection_record):
    """Listener do SQLAlchemy para habilitar o trace Oracle 10046 na conexão."""
    cursor = None  # Inicializa para garantir que exista no finally
    try:
        cursor = dbapi_connection.cursor()
        # Identificador único para o arquivo de trace no servidor Oracle
        # Adiciona o PID (Process ID) para ajudar a identificar qual processo gerou o trace
        trace_identifier = f"sqlalchemy_app_{os.getpid()}_{int(time.time())}"
        logging.info(f"*** HABILITANDO ORACLE TRACE (ID: {trace_identifier}) para nova conexão ***")

        # Define o identificador no servidor
        cursor.execute(f"ALTER SESSION SET TRACEFILE_IDENTIFIER = '{trace_identifier}'")
        # Habilita o trace 10046 (SQL, Binds, Waits)
        cursor.execute("ALTER SESSION SET EVENTS '10046 trace name context forever, level 12'")
        # Alternativa mais simples: cursor.execute("ALTER SESSION SET SQL_TRACE = TRUE")

    except Exception as e:
        logging.error(f"!!! Falha ao habilitar o trace Oracle na sessão: {e} !!!", exc_info=True)
    finally:
        # Garante que o cursor seja fechado mesmo se ocorrer um erro
        if cursor:
            try:
                cursor.close()
            except Exception as e_close:
                logging.error(
                    f"!!! Falha ao fechar o cursor no listener de trace: {e_close} !!!",
                    exc_info=True,
                )


# --- Criação do Engine SQLAlchemy ---
connection_string = f"oracle+oracledb://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/?service_name={SERVICE_NAME}"
logging.info(f"Criando engine SQLAlchemy para: oracle+oracledb://{USERNAME}:***@{HOST}:{PORT}/?service_name={SERVICE_NAME}")

engine_args = {
    "pool_timeout": 30,  # Tempo limite para obter conexão do pool
    "pool_recycle": 1800,  # Recicla conexões após 30 minutos (bom para firewalls)
}

if ENABLE_SQL_ALCHEMY_LOG:
    engine_args["echo"] = True  # Log do SQLAlchemy (SQL gerado), diferente do trace Oracle
    engine_args["echo_pool"] = "debug"  # Log detalhado do pool de conexões

engine = create_engine(connection_string, **engine_args)

# --- Registro Condicional do Listener de Trace ---
if ENABLE_ORACLE_TRACE_ENV:
    # Registra a função listener para o evento 'connect' do engine
    event.listen(engine, "connect", enable_oracle_trace_listener)
    logging.warning("<<< Trace Oracle (10046) HABILITADO via variável de ambiente ORACLE_ENABLE_TRACE=true >>>")
    logging.warning("Arquivos .trc serão gerados no DIAGNOSTIC_DEST do servidor Oracle.")
else:
    logging.info("Trace Oracle está DESABILITADO (ORACLE_ENABLE_TRACE não é 'true').")
