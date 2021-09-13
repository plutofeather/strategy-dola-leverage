import brownie
import pytest
import util
from brownie import Contract, Wei


# same test as profitable harvest except with different router
def test_router_change(
        accounts,
        token,
        vault,
        weth,
        delegatedVault,
        strategy,
        user,
        strategist,
        weth_whale,
        amount,
        RELATIVE_APPROX,
        chain,
        gov
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # 1000 eth, roughly 3m
    strategy.setBorrowLimit(1000 * 10 ** 18)

    # Harvest 1: Send funds through the strategy
    strategy.harvest({"from": strategist})
    assert (strategy.valueOfDelegated() > 0)  # ensure funds have been deposited into delegated vault
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # increase rewards, lending interest and borrowing interests
    # assets_before = vault.totalAssets()
    chain.sleep(30 * 24 * 3600)  # 30 days
    chain.mine(1)

    # change router to sushiswap
    strategy.setRouter("0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F", {'from': gov})

    strategy.harvest()
    weth.transfer(delegatedVault, Wei("20_000 ether"), {"from": weth_whale})  # simulate delegated vault interest

    # Harvest 2: Realize profit
    before_pps = vault.pricePerShare()
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    # print(
    #     "Estimated APR: ", "{:.2%}".format((vault.totalAssets() - assets_before) / assets_before * 12),
    # )

    profit = token.balanceOf(vault.address)  # Profits go to vault
    assert strategy.estimatedTotalAssets() + profit > amount
    assert vault.pricePerShare() > before_pps
    assert vault.totalAssets() > amount
