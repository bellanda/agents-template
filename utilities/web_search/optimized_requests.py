import atexit
import random
import time
from typing import Dict, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout
from urllib3.util.retry import Retry


class OptimizedSession:
    """Sessão otimizada do requests que simula comportamento real de navegador com timeouts baixos."""

    def __init__(self, timeout: tuple = (3, 5)):
        """
        Args:
            timeout: Tuple (connection_timeout, read_timeout) em segundos
        """
        self.session = requests.Session()
        self.timeout = timeout
        self._setup_session()

    def _get_random_user_agent(self) -> str:
        """Retorna um User-Agent aleatório de navegadores reais."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        return random.choice(user_agents)

    def _get_default_headers(self) -> Dict[str, str]:
        """Retorna headers padrão que navegadores reais enviam."""
        return {
            "User-Agent": self._get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,en-US;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Charset": "utf-8, iso-8859-1;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
        }

    def _setup_session(self):
        """Configura a sessão com timeouts baixos e sem retry agressivo."""
        # Headers padrão
        self.session.headers.update(self._get_default_headers())

        # Configuração de retry mínima - apenas 1 tentativa extra
        retry_strategy = Retry(
            total=1,  # Reduzido para apenas 1 retry
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=0.3,  # Backoff mais rápido
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )

        # Adaptador HTTP com retry mínimo
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Verificação SSL mais flexível
        self.session.verify = True

    def _handle_request_error(self, url: str, error: Exception) -> str:
        """Converte erros de request em strings descritivas."""
        if isinstance(error, Timeout):
            return f"TIMEOUT_ERROR: {url} - Request timed out"
        elif isinstance(error, ConnectionError):
            return f"CONNECTION_ERROR: {url} - Failed to connect"
        elif isinstance(error, HTTPError):
            return f"HTTP_ERROR: {url} - HTTP {error.response.status_code}"
        elif isinstance(error, RequestException):
            return f"REQUEST_ERROR: {url} - {str(error)}"
        else:
            return f"UNKNOWN_ERROR: {url} - {str(error)}"

    def get(
        self, url: str, delay: Optional[float] = None, timeout: Optional[tuple] = None, **kwargs
    ) -> Union[requests.Response, str]:
        """GET request otimizado com timeout baixo e tratamento de erro."""
        if delay:
            time.sleep(delay)

        # Usa timeout personalizado ou padrão da instância
        request_timeout = timeout or self.timeout

        # Atualiza User-Agent para cada request
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        if "User-Agent" not in kwargs["headers"]:
            kwargs["headers"]["User-Agent"] = self._get_random_user_agent()

        try:
            return self.session.get(url, timeout=request_timeout, **kwargs)
        except Exception as e:
            return self._handle_request_error(url, e)

    def post(
        self, url: str, delay: Optional[float] = None, timeout: Optional[tuple] = None, **kwargs
    ) -> Union[requests.Response, str]:
        """POST request otimizado com timeout baixo e tratamento de erro."""
        if delay:
            time.sleep(delay)

        # Usa timeout personalizado ou padrão da instância
        request_timeout = timeout or self.timeout

        # Headers específicos para POST
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"].update(
            {
                "User-Agent": self._get_random_user_agent(),
                "Content-Type": kwargs["headers"].get("Content-Type", "application/x-www-form-urlencoded"),
                "Origin": kwargs["headers"].get("Origin", url.split("/")[0] + "//" + url.split("/")[2]),
                "Referer": kwargs["headers"].get("Referer", url),
            }
        )

        try:
            return self.session.post(url, timeout=request_timeout, **kwargs)
        except Exception as e:
            return self._handle_request_error(url, e)

    def request(
        self, method: str, url: str, delay: Optional[float] = None, timeout: Optional[tuple] = None, **kwargs
    ) -> Union[requests.Response, str]:
        """Request genérico otimizado com timeout baixo e tratamento de erro."""
        if delay:
            time.sleep(delay)

        # Usa timeout personalizado ou padrão da instância
        request_timeout = timeout or self.timeout

        if "headers" not in kwargs:
            kwargs["headers"] = {}
        if "User-Agent" not in kwargs["headers"]:
            kwargs["headers"]["User-Agent"] = self._get_random_user_agent()

        try:
            return self.session.request(method, url, timeout=request_timeout, **kwargs)
        except Exception as e:
            return self._handle_request_error(url, e)

    def close(self):
        """Fecha a sessão."""
        self.session.close()


# Instância global da sessão otimizada com timeout baixo
_optimized_session = OptimizedSession(timeout=(2, 3))


# Funções de conveniência que usam a sessão otimizada
def get(url: str, delay: Optional[float] = None, timeout: Optional[tuple] = None, **kwargs) -> Union[requests.Response, str]:
    """GET request otimizado que simula comportamento real de navegador com timeout baixo.

    Args:
        url: URL para fazer o request
        delay: Delay em segundos antes do request (simula comportamento humano)
        timeout: Tuple (connection_timeout, read_timeout) em segundos. Default: (3, 5)
        **kwargs: Argumentos adicionais para requests.get

    Returns:
        Response object do requests ou string com erro
    """
    return _optimized_session.get(url, delay=delay, timeout=timeout, **kwargs)


def post(
    url: str, delay: Optional[float] = None, timeout: Optional[tuple] = None, **kwargs
) -> Union[requests.Response, str]:
    """POST request otimizado que simula comportamento real de navegador com timeout baixo.

    Args:
        url: URL para fazer o request
        delay: Delay em segundos antes do request
        timeout: Tuple (connection_timeout, read_timeout) em segundos. Default: (3, 5)
        **kwargs: Argumentos adicionais para requests.post

    Returns:
        Response object do requests ou string com erro
    """
    return _optimized_session.post(url, delay=delay, timeout=timeout, **kwargs)


def request(
    method: str, url: str, delay: Optional[float] = None, timeout: Optional[tuple] = None, **kwargs
) -> Union[requests.Response, str]:
    """Request genérico otimizado que simula comportamento real de navegador com timeout baixo.

    Args:
        method: Método HTTP (GET, POST, etc.)
        url: URL para fazer o request
        delay: Delay em segundos antes do request
        timeout: Tuple (connection_timeout, read_timeout) em segundos. Default: (3, 5)
        **kwargs: Argumentos adicionais para requests.request

    Returns:
        Response object do requests ou string com erro
    """
    return _optimized_session.request(method, url, delay=delay, timeout=timeout, **kwargs)


def new_session(timeout: tuple = (3, 5)) -> OptimizedSession:
    """Cria uma nova sessão otimizada independente.

    Args:
        timeout: Tuple (connection_timeout, read_timeout) em segundos

    Returns:
        Nova instância de OptimizedSession
    """
    return OptimizedSession(timeout=timeout)


def is_error_response(response: Union[requests.Response, str]) -> bool:
    """Verifica se a resposta é um erro (string) ou sucesso (Response).

    Args:
        response: Resposta do request

    Returns:
        True se for erro, False se for Response válido
    """
    return isinstance(response, str)


def get_error_message(response: Union[requests.Response, str]) -> Optional[str]:
    """Extrai mensagem de erro se a resposta for um erro.

    Args:
        response: Resposta do request

    Returns:
        Mensagem de erro ou None se for Response válido
    """
    return response if isinstance(response, str) else None


# Função para simular delay humano aleatório mais rápido
def human_delay(min_seconds: float = 0.1, max_seconds: float = 0.5) -> float:
    """Gera um delay aleatório para simular comportamento humano (mais rápido).

    Args:
        min_seconds: Tempo mínimo de delay
        max_seconds: Tempo máximo de delay

    Returns:
        Tempo de delay em segundos
    """
    return random.uniform(min_seconds, max_seconds)


# Limpeza automática ao sair
atexit.register(_optimized_session.close)
