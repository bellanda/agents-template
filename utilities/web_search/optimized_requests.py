import atexit
import random
import time
from typing import Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class OptimizedSession:
    """Sessão otimizada do requests que simula comportamento real de navegador."""

    def __init__(self):
        self.session = requests.Session()
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
        """Configura a sessão com as melhores práticas."""
        # Headers padrão
        self.session.headers.update(self._get_default_headers())

        # Configuração de retry com backoff exponencial
        retry_strategy = Retry(
            total=3, status_forcelist=[429, 500, 502, 503, 504], backoff_factor=1, allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        # Adaptador HTTP com retry
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Configurações de timeout padrão
        self.session.timeout = (10, 30)  # (connection_timeout, read_timeout)

        # Verificação SSL mais flexível (cuidado em produção)
        self.session.verify = True

        # Pool de conexões otimizado
        self.session.adapters["http://"].poolmanager.connection_pool_kw.update({"maxsize": 20, "block": True})
        self.session.adapters["https://"].poolmanager.connection_pool_kw.update({"maxsize": 20, "block": True})

    def get(self, url: str, delay: Optional[float] = None, **kwargs) -> requests.Response:
        """GET request otimizado com delay opcional."""
        if delay:
            time.sleep(delay)

        # Atualiza User-Agent para cada request
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        if "User-Agent" not in kwargs["headers"]:
            kwargs["headers"]["User-Agent"] = self._get_random_user_agent()

        return self.session.get(url, **kwargs)

    def post(self, url: str, delay: Optional[float] = None, **kwargs) -> requests.Response:
        """POST request otimizado com delay opcional."""
        if delay:
            time.sleep(delay)

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

        return self.session.post(url, **kwargs)

    def request(self, method: str, url: str, delay: Optional[float] = None, **kwargs) -> requests.Response:
        """Request genérico otimizado."""
        if delay:
            time.sleep(delay)

        if "headers" not in kwargs:
            kwargs["headers"] = {}
        if "User-Agent" not in kwargs["headers"]:
            kwargs["headers"]["User-Agent"] = self._get_random_user_agent()

        return self.session.request(method, url, **kwargs)

    def close(self):
        """Fecha a sessão."""
        self.session.close()


# Instância global da sessão otimizada
_optimized_session = OptimizedSession()


# Funções de conveniência que usam a sessão otimizada
def get(url: str, delay: Optional[float] = None, **kwargs) -> requests.Response:
    """GET request otimizado que simula comportamento real de navegador.

    Args:
        url: URL para fazer o request
        delay: Delay em segundos antes do request (simula comportamento humano)
        **kwargs: Argumentos adicionais para requests.get

    Returns:
        Response object do requests
    """
    return _optimized_session.get(url, delay=delay, **kwargs)


def post(url: str, delay: Optional[float] = None, **kwargs) -> requests.Response:
    """POST request otimizado que simula comportamento real de navegador.

    Args:
        url: URL para fazer o request
        delay: Delay em segundos antes do request
        **kwargs: Argumentos adicionais para requests.post

    Returns:
        Response object do requests
    """
    return _optimized_session.post(url, delay=delay, **kwargs)


def request(method: str, url: str, delay: Optional[float] = None, **kwargs) -> requests.Response:
    """Request genérico otimizado que simula comportamento real de navegador.

    Args:
        method: Método HTTP (GET, POST, etc.)
        url: URL para fazer o request
        delay: Delay em segundos antes do request
        **kwargs: Argumentos adicionais para requests.request

    Returns:
        Response object do requests
    """
    return _optimized_session.request(method, url, delay=delay, **kwargs)


def new_session() -> OptimizedSession:
    """Cria uma nova sessão otimizada independente.

    Returns:
        Nova instância de OptimizedSession
    """
    return OptimizedSession()


# Função para simular delay humano aleatório
def human_delay(min_seconds: float = 0.5, max_seconds: float = 2.0) -> float:
    """Gera um delay aleatório para simular comportamento humano.

    Args:
        min_seconds: Tempo mínimo de delay
        max_seconds: Tempo máximo de delay

    Returns:
        Tempo de delay em segundos
    """
    return random.uniform(min_seconds, max_seconds)


# Limpeza automática ao sair
atexit.register(_optimized_session.close)
