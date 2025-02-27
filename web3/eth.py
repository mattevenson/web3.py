import asyncio
from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    NoReturn,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
    overload,
)
import warnings

from eth_account import (
    Account,
)
from eth_typing import (
    Address,
    BlockNumber,
    ChecksumAddress,
    HexStr,
)
from eth_utils import (
    is_checksum_address,
    is_string,
)
from eth_utils.toolz import (
    assoc,
    merge,
)
from hexbytes import (
    HexBytes,
)

from web3._utils.blocks import (
    select_method_for_block_identifier,
)
from web3._utils.empty import (
    Empty,
    empty,
)
from web3._utils.encoding import (
    to_hex,
)
from web3._utils.fee_utils import (
    async_fee_history_priority_fee,
    fee_history_priority_fee,
)
from web3._utils.filters import (
    select_filter_method,
)
from web3._utils.rpc_abi import (
    RPC,
)
from web3._utils.threads import (
    Timeout,
)
from web3._utils.transactions import (
    assert_valid_transaction_params,
    extract_valid_transaction_params,
    get_required_transaction,
    replace_transaction,
)
from web3.contract import (
    ConciseContract,
    Contract,
    ContractCaller,
)
from web3.exceptions import (
    TimeExhausted,
    TransactionNotFound,
)
from web3.iban import (
    Iban,
)
from web3.method import (
    Method,
    default_root_munger,
)
from web3.module import (
    Module,
)
from web3.types import (
    ENS,
    BlockData,
    BlockIdentifier,
    BlockParams,
    CallOverrideParams,
    FeeHistory,
    FilterParams,
    GasPriceStrategy,
    LogReceipt,
    MerkleProof,
    Nonce,
    SignedTx,
    SyncStatus,
    TxData,
    TxParams,
    TxReceipt,
    Uncle,
    Wei,
    _Hash32,
)


class BaseEth(Module):
    _default_account: Union[ChecksumAddress, Empty] = empty
    _default_block: BlockIdentifier = "latest"
    gasPriceStrategy = None

    _gas_price: Method[Callable[[], Wei]] = Method(
        RPC.eth_gasPrice,
        is_property=True,
    )

    @property
    def default_block(self) -> BlockIdentifier:
        return self._default_block

    @default_block.setter
    def default_block(self, value: BlockIdentifier) -> None:
        self._default_block = value

    @property
    def default_account(self) -> Union[ChecksumAddress, Empty]:
        return self._default_account

    @default_account.setter
    def default_account(self, account: Union[ChecksumAddress, Empty]) -> None:
        self._default_account = account

    def send_transaction_munger(self, transaction: TxParams) -> Tuple[TxParams]:
        if 'from' not in transaction and is_checksum_address(self.default_account):
            transaction = assoc(transaction, 'from', self.default_account)

        return (transaction,)

    _send_transaction: Method[Callable[[TxParams], HexBytes]] = Method(
        RPC.eth_sendTransaction,
        mungers=[send_transaction_munger]
    )

    _send_raw_transaction: Method[Callable[[Union[HexStr, bytes]], HexBytes]] = Method(
        RPC.eth_sendRawTransaction,
        mungers=[default_root_munger],
    )

    _get_transaction: Method[Callable[[_Hash32], TxData]] = Method(
        RPC.eth_getTransactionByHash,
        mungers=[default_root_munger]
    )

    _get_raw_transaction: Method[Callable[[_Hash32], HexBytes]] = Method(
        RPC.eth_getRawTransactionByHash,
        mungers=[default_root_munger]
    )

    """
    `eth_getRawTransactionByBlockHashAndIndex`
    `eth_getRawTransactionByBlockNumberAndIndex`
    """
    _get_raw_transaction_by_block: Method[Callable[[BlockIdentifier, int], HexBytes]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getRawTransactionByBlockNumberAndIndex,
            if_hash=RPC.eth_getRawTransactionByBlockHashAndIndex,
            if_number=RPC.eth_getRawTransactionByBlockNumberAndIndex,
        ),
        mungers=[default_root_munger]
    )

    def _generate_gas_price(self, transaction_params: Optional[TxParams] = None) -> Optional[Wei]:
        if self.gasPriceStrategy:
            return self.gasPriceStrategy(self.w3, transaction_params)
        return None

    def set_gas_price_strategy(self, gas_price_strategy: GasPriceStrategy) -> None:
        self.gasPriceStrategy = gas_price_strategy

    def estimate_gas_munger(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None
    ) -> Sequence[Union[TxParams, BlockIdentifier]]:
        if 'from' not in transaction and is_checksum_address(self.default_account):
            transaction = assoc(transaction, 'from', self.default_account)

        if block_identifier is None:
            params: Sequence[Union[TxParams, BlockIdentifier]] = [transaction]
        else:
            params = [transaction, block_identifier]

        return params

    _estimate_gas: Method[Callable[..., int]] = Method(
        RPC.eth_estimateGas,
        mungers=[estimate_gas_munger]
    )

    _fee_history: Method[Callable[..., FeeHistory]] = Method(
        RPC.eth_feeHistory,
        mungers=[default_root_munger]
    )

    _max_priority_fee: Method[Callable[..., Wei]] = Method(
        RPC.eth_maxPriorityFeePerGas,
        is_property=True,
    )

    def get_block_munger(
        self, block_identifier: BlockIdentifier, full_transactions: bool = False
    ) -> Tuple[BlockIdentifier, bool]:
        return (block_identifier, full_transactions)

    """
    `eth_getBlockByHash`
    `eth_getBlockByNumber`
    """
    _get_block: Method[Callable[..., BlockData]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getBlockByNumber,
            if_hash=RPC.eth_getBlockByHash,
            if_number=RPC.eth_getBlockByNumber,
        ),
        mungers=[get_block_munger],
    )

    get_block_number: Method[Callable[[], BlockNumber]] = Method(
        RPC.eth_blockNumber,
        is_property=True,
    )

    get_coinbase: Method[Callable[[], ChecksumAddress]] = Method(
        RPC.eth_coinbase,
        is_property=True,
    )

    def block_id_munger(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None
    ) -> Tuple[Union[Address, ChecksumAddress, ENS], BlockIdentifier]:
        if block_identifier is None:
            block_identifier = self.default_block
        return (account, block_identifier)

    def get_storage_at_munger(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        position: int,
        block_identifier: Optional[BlockIdentifier] = None
    ) -> Tuple[Union[Address, ChecksumAddress, ENS], int, BlockIdentifier]:
        if block_identifier is None:
            block_identifier = self.default_block
        return (account, position, block_identifier)

    def call_munger(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[CallOverrideParams] = None,
    ) -> Union[Tuple[TxParams, BlockIdentifier], Tuple[TxParams, BlockIdentifier, CallOverrideParams]]:  # noqa-E501
        # TODO: move to middleware
        if 'from' not in transaction and is_checksum_address(self.default_account):
            transaction = assoc(transaction, 'from', self.default_account)

        # TODO: move to middleware
        if block_identifier is None:
            block_identifier = self.default_block

        if state_override is None:
            return (transaction, block_identifier)
        else:
            return (transaction, block_identifier, state_override)

    _get_accounts: Method[Callable[[], Tuple[ChecksumAddress]]] = Method(
        RPC.eth_accounts,
        is_property=True,
    )

    _get_hashrate: Method[Callable[[], int]] = Method(
        RPC.eth_hashrate,
        is_property=True,
    )

    _chain_id: Method[Callable[[], int]] = Method(
        RPC.eth_chainId,
        is_property=True,
    )

    _is_mining: Method[Callable[[], bool]] = Method(
        RPC.eth_mining,
        is_property=True,
    )

    _is_syncing: Method[Callable[[], Union[SyncStatus, bool]]] = Method(
        RPC.eth_syncing,
        is_property=True,
    )

    _get_transaction_receipt: Method[Callable[[_Hash32], TxReceipt]] = Method(
        RPC.eth_getTransactionReceipt,
        mungers=[default_root_munger]
    )


class AsyncEth(BaseEth):
    is_async = True
    defaultContractFactory: Type[Union[Contract, ConciseContract, ContractCaller]] = Contract

    @property
    async def accounts(self) -> Tuple[ChecksumAddress]:
        return await self._get_accounts()  # type: ignore

    @property
    async def block_number(self) -> BlockNumber:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self.get_block_number()  # type: ignore

    @property
    async def chain_id(self) -> int:
        return await self._chain_id()  # type: ignore

    @property
    async def coinbase(self) -> ChecksumAddress:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self.get_coinbase()  # type: ignore

    @property
    async def gas_price(self) -> Wei:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self._gas_price()  # type: ignore

    @property
    async def hashrate(self) -> int:
        return await self._get_hashrate()  # type: ignore

    @property
    async def max_priority_fee(self) -> Wei:
        """
        Try to use eth_maxPriorityFeePerGas but, since this is not part of the spec and is only
        supported by some clients, fall back to an eth_feeHistory calculation with min and max caps.
        """
        try:
            return await self._max_priority_fee()  # type: ignore
        except ValueError:
            warnings.warn(
                "There was an issue with the method eth_maxPriorityFeePerGas. Calculating using "
                "eth_feeHistory."
            )
            return await async_fee_history_priority_fee(self)

    @property
    async def mining(self) -> bool:
        return await self._is_mining()  # type: ignore

    @property
    async def syncing(self) -> Union[SyncStatus, bool]:
        return await self._is_syncing()  # type: ignore

    async def fee_history(
            self,
            block_count: int,
            newest_block: Union[BlockParams, BlockNumber],
            reward_percentiles: Optional[List[float]] = None
    ) -> FeeHistory:
        return await self._fee_history(  # type: ignore
            block_count, newest_block, reward_percentiles)

    async def send_transaction(self, transaction: TxParams) -> HexBytes:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self._send_transaction(transaction)  # type: ignore

    async def send_raw_transaction(self, transaction: Union[HexStr, bytes]) -> HexBytes:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self._send_raw_transaction(transaction)  # type: ignore

    async def get_transaction(self, transaction_hash: _Hash32) -> TxData:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self._get_transaction(transaction_hash)  # type: ignore

    async def get_raw_transaction(self, transaction_hash: _Hash32) -> TxData:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self._get_raw_transaction(transaction_hash)  # type: ignore

    async def get_raw_transaction_by_block(
        self, block_identifier: BlockIdentifier, index: int
    ) -> HexBytes:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self._get_raw_transaction_by_block(block_identifier, index)  # type: ignore

    async def generate_gas_price(
        self, transaction_params: Optional[TxParams] = None
    ) -> Optional[Wei]:
        return self._generate_gas_price(transaction_params)

    async def estimate_gas(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None
    ) -> int:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self._estimate_gas(transaction, block_identifier)  # type: ignore

    async def get_block(
        self, block_identifier: BlockIdentifier, full_transactions: bool = False
    ) -> BlockData:
        # types ignored b/c mypy conflict with BlockingEth properties
        return await self._get_block(block_identifier, full_transactions)  # type: ignore

    _get_balance: Method[Callable[..., Awaitable[Wei]]] = Method(
        RPC.eth_getBalance,
        mungers=[BaseEth.block_id_munger],
    )

    async def get_balance(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None
    ) -> Wei:
        return await self._get_balance(account, block_identifier)

    _get_code: Method[Callable[..., Awaitable[HexBytes]]] = Method(
        RPC.eth_getCode,
        mungers=[BaseEth.block_id_munger]
    )

    async def get_code(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None
    ) -> HexBytes:
        return await self._get_code(account, block_identifier)

    _get_logs: Method[Callable[[FilterParams], Awaitable[List[LogReceipt]]]] = Method(
        RPC.eth_getLogs,
        mungers=[default_root_munger]
    )

    async def get_logs(
        self,
        filter_params: FilterParams,
    ) -> List[LogReceipt]:
        return await self._get_logs(filter_params)

    _get_transaction_count: Method[Callable[..., Awaitable[Nonce]]] = Method(
        RPC.eth_getTransactionCount,
        mungers=[BaseEth.block_id_munger],
    )

    async def get_transaction_count(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        block_identifier: Optional[BlockIdentifier] = None
    ) -> Nonce:
        return await self._get_transaction_count(account, block_identifier)

    _call: Method[Callable[..., Awaitable[Union[bytes, bytearray]]]] = Method(
        RPC.eth_call,
        mungers=[BaseEth.call_munger]
    )

    async def get_transaction_receipt(
        self, transaction_hash: _Hash32
    ) -> TxReceipt:
        return await self._get_transaction_receipt(transaction_hash)  # type: ignore

    async def wait_for_transaction_receipt(
        self, transaction_hash: _Hash32, timeout: float = 120, poll_latency: float = 0.1
    ) -> TxReceipt:
        async def _wait_for_tx_receipt_with_timeout(
            _tx_hash: _Hash32, _poll_latence: float
        ) -> TxReceipt:
            while True:
                try:
                    tx_receipt = await self._get_transaction_receipt(_tx_hash)  # type: ignore
                except TransactionNotFound:
                    tx_receipt = None
                if tx_receipt is not None:
                    break
                await asyncio.sleep(poll_latency)
            return tx_receipt
        try:
            return await asyncio.wait_for(
                _wait_for_tx_receipt_with_timeout(transaction_hash, poll_latency),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise TimeExhausted(
                f"Transaction {HexBytes(transaction_hash) !r} is not in the chain "
                f"after {timeout} seconds"
            )

    _get_storage_at: Method[Callable[..., Awaitable[HexBytes]]] = Method(
        RPC.eth_getStorageAt,
        mungers=[BaseEth.get_storage_at_munger],
    )

    async def get_storage_at(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        position: int,
        block_identifier: Optional[BlockIdentifier] = None
    ) -> HexBytes:
        return await self._get_storage_at(account, position, block_identifier)

    async def call(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None,
        state_override: Optional[CallOverrideParams] = None,
    ) -> Union[bytes, bytearray]:
        return await self._call(transaction, block_identifier, state_override)

    @overload
    def contract(self, address: None = None, **kwargs: Any) -> Type[Contract]: ...  # noqa: E704,E501

    @overload  # noqa: F811
    def contract( self, address: Union[Address, ChecksumAddress, ENS], **kwargs: Any) -> Contract:...  # noqa: E704,E501

    def contract(  # noqa: F811
        self,
        address: Optional[Union[Address, ChecksumAddress, ENS]] = None,
        **kwargs: Any,
    ) -> Union[Type[Contract], Contract]:
        ContractFactoryClass = kwargs.pop(
            "ContractFactoryClass", self.defaultContractFactory
        )

        ContractFactory = ContractFactoryClass.factory(self.w3, **kwargs)

        if address:
            return ContractFactory(address)
        else:
            return ContractFactory

    @deprecated_for("set_contract_factory")
    def setContractFactory(
        self, contractFactory: Type[Union[Contract, ConciseContract, ContractCaller]]
    ) -> None:
        return self.set_contract_factory(contractFactory)

    def set_contract_factory(
        self, contractFactory: Type[Union[Contract, ConciseContract, ContractCaller]]
    ) -> None:
        self.defaultContractFactory = contractFactory

    def getCompilers(self) -> NoReturn:
        raise DeprecationWarning("This method has been deprecated as of EIP 1474.")


class Eth(BaseEth):
    account = Account()
    defaultContractFactory: Type[Union[Contract, ConciseContract, ContractCaller]] = Contract  # noqa: E704,E501
    iban = Iban

    def namereg(self) -> NoReturn:
        raise NotImplementedError()

    def icapNamereg(self) -> NoReturn:
        raise NotImplementedError()

    @property
    def syncing(self) -> Union[SyncStatus, bool]:
        return self._is_syncing()

    @property
    def coinbase(self) -> ChecksumAddress:
        return self.get_coinbase()

    @property
    def mining(self) -> bool:
        return self._is_mining()

    @property
    def hashrate(self) -> int:
        return self._get_hashrate()

    @property
    def gas_price(self) -> Wei:
        return self._gas_price()

    @property
    def accounts(self) -> Tuple[ChecksumAddress]:
        return self._get_accounts()

    @property
    def block_number(self) -> BlockNumber:
        return self.get_block_number()

    @property
    def chain_id(self) -> int:
        return self._chain_id()

    get_balance: Method[Callable[..., Wei]] = Method(
        RPC.eth_getBalance,
        mungers=[BaseEth.block_id_munger],
    )

    @property
    def max_priority_fee(self) -> Wei:
        """
        Try to use eth_maxPriorityFeePerGas but, since this is not part of the spec and is only
        supported by some clients, fall back to an eth_feeHistory calculation with min and max caps.
        """
        try:
            return self._max_priority_fee()
        except ValueError:
            warnings.warn(
                "There was an issue with the method eth_maxPriorityFeePerGas. Calculating using "
                "eth_feeHistory."
            )
            return fee_history_priority_fee(self)

    get_storage_at: Method[Callable[..., HexBytes]] = Method(
        RPC.eth_getStorageAt,
        mungers=[BaseEth.get_storage_at_munger],
    )

    def get_proof_munger(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        positions: Sequence[int],
        block_identifier: Optional[BlockIdentifier] = None
    ) -> Tuple[Union[Address, ChecksumAddress, ENS], Sequence[int], Optional[BlockIdentifier]]:
        if block_identifier is None:
            block_identifier = self.default_block
        return (account, positions, block_identifier)

    get_proof: Method[
        Callable[
            [Tuple[Union[Address, ChecksumAddress, ENS], Sequence[int], Optional[BlockIdentifier]]],
            MerkleProof
        ]
    ] = Method(
        RPC.eth_getProof,
        mungers=[get_proof_munger],
    )

    def get_block(
        self, block_identifier: BlockIdentifier, full_transactions: bool = False
    ) -> BlockData:
        return self._get_block(block_identifier, full_transactions)

    get_code: Method[Callable[..., HexBytes]] = Method(
        RPC.eth_getCode,
        mungers=[BaseEth.block_id_munger]
    )

    """
    `eth_getBlockTransactionCountByHash`
    `eth_getBlockTransactionCountByNumber`
    """
    get_block_transaction_count: Method[Callable[[BlockIdentifier], int]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getBlockTransactionCountByNumber,
            if_hash=RPC.eth_getBlockTransactionCountByHash,
            if_number=RPC.eth_getBlockTransactionCountByNumber,
        ),
        mungers=[default_root_munger]
    )

    """
    `eth_getUncleCountByBlockHash`
    `eth_getUncleCountByBlockNumber`
    """
    get_uncle_count: Method[Callable[[BlockIdentifier], int]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getUncleCountByBlockNumber,
            if_hash=RPC.eth_getUncleCountByBlockHash,
            if_number=RPC.eth_getUncleCountByBlockNumber,
        ),
        mungers=[default_root_munger]
    )

    """
    `eth_getUncleByBlockHashAndIndex`
    `eth_getUncleByBlockNumberAndIndex`
    """
    get_uncle_by_block: Method[Callable[[BlockIdentifier, int], Uncle]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getUncleByBlockNumberAndIndex,
            if_hash=RPC.eth_getUncleByBlockHashAndIndex,
            if_number=RPC.eth_getUncleByBlockNumberAndIndex,
        ),
        mungers=[default_root_munger]
    )

    def get_transaction(self, transaction_hash: _Hash32) -> TxData:
        return self._get_transaction(transaction_hash)

    def get_raw_transaction(self, transaction_hash: _Hash32) -> _Hash32:
        return self._get_raw_transaction(transaction_hash)

    def get_raw_transaction_by_block(
        self, block_identifier: BlockIdentifier, index: int
    ) -> HexBytes:
        return self._get_raw_transaction_by_block(block_identifier, index)

    get_transaction_by_block: Method[Callable[[BlockIdentifier, int], TxData]] = Method(
        method_choice_depends_on_args=select_method_for_block_identifier(
            if_predefined=RPC.eth_getTransactionByBlockNumberAndIndex,
            if_hash=RPC.eth_getTransactionByBlockHashAndIndex,
            if_number=RPC.eth_getTransactionByBlockNumberAndIndex,
        ),
        mungers=[default_root_munger]
    )

    def wait_for_transaction_receipt(
        self, transaction_hash: _Hash32, timeout: float = 120, poll_latency: float = 0.1
    ) -> TxReceipt:
        try:
            with Timeout(timeout) as _timeout:
                while True:
                    try:
                        tx_receipt = self._get_transaction_receipt(transaction_hash)
                    except TransactionNotFound:
                        tx_receipt = None
                    if tx_receipt is not None:
                        break
                    _timeout.sleep(poll_latency)
            return tx_receipt

        except Timeout:
            raise TimeExhausted(
                f"Transaction {HexBytes(transaction_hash) !r} is not in the chain "
                f"after {timeout} seconds"
            )

    def get_transaction_receipt(
        self, transaction_hash: _Hash32
    ) -> TxReceipt:
        return self._get_transaction_receipt(transaction_hash)

    get_transaction_count: Method[Callable[..., Nonce]] = Method(
        RPC.eth_getTransactionCount,
        mungers=[BaseEth.block_id_munger],
    )

    def replace_transaction(self, transaction_hash: _Hash32, new_transaction: TxParams) -> HexBytes:
        current_transaction = get_required_transaction(self.w3, transaction_hash)
        return replace_transaction(self.w3, current_transaction, new_transaction)

    # todo: Update Any to stricter kwarg checking with TxParams
    # https://github.com/python/mypy/issues/4441
    def modify_transaction(
        self, transaction_hash: _Hash32, **transaction_params: Any
    ) -> HexBytes:
        assert_valid_transaction_params(cast(TxParams, transaction_params))
        current_transaction = get_required_transaction(self.w3, transaction_hash)
        current_transaction_params = extract_valid_transaction_params(current_transaction)
        new_transaction = merge(current_transaction_params, transaction_params)
        return replace_transaction(self.w3, current_transaction, new_transaction)

    def send_transaction(self, transaction: TxParams) -> HexBytes:
        return self._send_transaction(transaction)

    def send_raw_transaction(self, transaction: Union[HexStr, bytes]) -> HexBytes:
        return self._send_raw_transaction(transaction)

    def sign_munger(
        self,
        account: Union[Address, ChecksumAddress, ENS],
        data: Union[int, bytes] = None,
        hexstr: HexStr = None,
        text: str = None
    ) -> Tuple[Union[Address, ChecksumAddress, ENS], HexStr]:
        message_hex = to_hex(data, hexstr=hexstr, text=text)
        return (account, message_hex)

    sign: Method[Callable[..., HexStr]] = Method(
        RPC.eth_sign,
        mungers=[sign_munger],
    )

    sign_transaction: Method[Callable[[TxParams], SignedTx]] = Method(
        RPC.eth_signTransaction,
        mungers=[default_root_munger],
    )

    sign_typed_data: Method[Callable[..., HexStr]] = Method(
        RPC.eth_signTypedData,
        mungers=[default_root_munger],
    )

    call: Method[Callable[..., Union[bytes, bytearray]]] = Method(
        RPC.eth_call,
        mungers=[BaseEth.call_munger]
    )

    def estimate_gas(
        self,
        transaction: TxParams,
        block_identifier: Optional[BlockIdentifier] = None
    ) -> int:
        return self._estimate_gas(transaction, block_identifier)

    def fee_history(
        self,
        block_count: int,
        newest_block: Union[BlockParams, BlockNumber],
        reward_percentiles: Optional[List[float]] = None
    ) -> FeeHistory:
        return self._fee_history(block_count, newest_block, reward_percentiles)

    def filter_munger(
        self,
        filter_params: Optional[Union[str, FilterParams]] = None,
        filter_id: Optional[HexStr] = None
    ) -> Union[List[FilterParams], List[HexStr], List[str]]:
        if filter_id and filter_params:
            raise TypeError(
                "Ambiguous invocation: provide either a `filter_params` or a `filter_id` argument. "
                "Both were supplied."
            )
        if isinstance(filter_params, dict):
            return [filter_params]
        elif is_string(filter_params):
            if filter_params in ['latest', 'pending']:
                return [filter_params]
            else:
                raise ValueError(
                    "The filter API only accepts the values of `pending` or "
                    "`latest` for string based filters"
                )
        elif filter_id and not filter_params:
            return [filter_id]
        else:
            raise TypeError("Must provide either filter_params as a string or "
                            "a valid filter object, or a filter_id as a string "
                            "or hex.")

    filter: Method[Callable[..., Any]] = Method(
        method_choice_depends_on_args=select_filter_method(
            if_new_block_filter=RPC.eth_newBlockFilter,
            if_new_pending_transaction_filter=RPC.eth_newPendingTransactionFilter,
            if_new_filter=RPC.eth_newFilter,
        ),
        mungers=[filter_munger],
    )

    get_filter_changes: Method[Callable[[HexStr], List[LogReceipt]]] = Method(
        RPC.eth_getFilterChanges,
        mungers=[default_root_munger]
    )

    get_filter_logs: Method[Callable[[HexStr], List[LogReceipt]]] = Method(
        RPC.eth_getFilterLogs,
        mungers=[default_root_munger]
    )

    get_logs: Method[Callable[[FilterParams], List[LogReceipt]]] = Method(
        RPC.eth_getLogs,
        mungers=[default_root_munger]
    )

    submit_hashrate: Method[Callable[[int, _Hash32], bool]] = Method(
        RPC.eth_submitHashrate,
        mungers=[default_root_munger],
    )

    submit_work: Method[Callable[[int, _Hash32, _Hash32], bool]] = Method(
        RPC.eth_submitWork,
        mungers=[default_root_munger],
    )

    uninstall_filter: Method[Callable[[HexStr], bool]] = Method(
        RPC.eth_uninstallFilter,
        mungers=[default_root_munger],
    )

    @overload
    def contract(self, address: None = None, **kwargs: Any) -> Type[Contract]: ...  # noqa: E704,E501

    @overload  # noqa: F811
    def contract(self, address: Union[Address, ChecksumAddress, ENS], **kwargs: Any) -> Contract: ...  # noqa: E704,E501

    def contract(  # noqa: F811
        self, address: Optional[Union[Address, ChecksumAddress, ENS]] = None, **kwargs: Any
    ) -> Union[Type[Contract], Contract]:
        ContractFactoryClass = kwargs.pop('ContractFactoryClass', self.defaultContractFactory)

        ContractFactory = ContractFactoryClass.factory(self.w3, **kwargs)

        if address:
            return ContractFactory(address)
        else:
            return ContractFactory

    def set_contract_factory(
        self, contractFactory: Type[Union[Contract, ConciseContract, ContractCaller]]
    ) -> None:
        self.defaultContractFactory = contractFactory

    get_work: Method[Callable[[], List[HexBytes]]] = Method(
        RPC.eth_getWork,
        is_property=True,
    )

    def generate_gas_price(self, transaction_params: Optional[TxParams] = None) -> Optional[Wei]:
        return self._generate_gas_price(transaction_params)
