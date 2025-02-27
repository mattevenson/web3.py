
import pkg_resources

from eth_account import (
    Account  # noqa: E402,
)
from web3.main import (
    Web3  # noqa: E402,
)
from web3.providers.eth_tester import (  # noqa: E402
    EthereumTesterProvider,
)
from web3.providers.ipc import (  # noqa: E402
    IPCProvider,
)
from web3.providers.rpc import (  # noqa: E402
    HTTPProvider,
)
from web3.providers.async_rpc import (  # noqa: E402
    AsyncHTTPProvider,
    BatchedAsyncHTTPProvider,
)
from web3.providers.websocket import (  # noqa: E402
    WebsocketProvider,
)

__version__ = pkg_resources.get_distribution("web3").version

__all__ = [
    "__version__",
    "Web3",
    "HTTPProvider",
    "IPCProvider",
    "WebsocketProvider",
    "EthereumTesterProvider",
    "Account",
    "AsyncHTTPProvider",
    "BatchedAsyncHTTPProvider",
]
