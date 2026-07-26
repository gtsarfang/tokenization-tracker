"""Shared web3 helper for reading ERC-20 total supply. Reusable by any future
asset-class source that reads token supply directly from a contract."""

from __future__ import annotations

from dataclasses import dataclass

from web3 import Web3
from web3.exceptions import Web3Exception

from reality_check.models import DataQuality

_ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]


@dataclass(frozen=True)
class SupplyReading:
    quantity: float
    quality: DataQuality
    note: str


def get_web3(rpc_url: str, timeout_seconds: float) -> Web3:
    return Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout_seconds}))


def read_erc20_total_supply(
    w3: Web3,
    contract_address: str,
    expected_decimals: int,
    fallback_quantity: float,
) -> SupplyReading:
    """Reads decimals() and totalSupply() from an ERC-20 contract, returning the
    supply already adjusted for decimals.

    Falls back to `fallback_quantity` (marked FALLBACK) on any connection error,
    timeout, or contract call failure, and also if the on-chain `decimals()` value
    disagrees with `expected_decimals` — treated as a data-integrity red flag rather
    than trusted, since it would silently corrupt the value calculation.
    """
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address), abi=_ERC20_ABI
        )
        decimals = contract.functions.decimals().call()
        if decimals != expected_decimals:
            return SupplyReading(
                quantity=fallback_quantity,
                quality=DataQuality.FALLBACK,
                note=(
                    f"on-chain decimals()={decimals} disagreed with expected "
                    f"{expected_decimals}; used fallback supply"
                ),
            )
        raw_supply = contract.functions.totalSupply().call()
        quantity = raw_supply / (10**decimals)
        return SupplyReading(quantity=quantity, quality=DataQuality.LIVE, note="")
    except (Web3Exception, OSError, ValueError) as exc:
        return SupplyReading(
            quantity=fallback_quantity,
            quality=DataQuality.FALLBACK,
            note=f"on-chain read failed ({exc.__class__.__name__}); used fallback supply",
        )
