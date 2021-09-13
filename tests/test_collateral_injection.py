import brownie
import pytest
import util
from brownie import Contract, Wei


def test_profitable_harvest_with_collateral_injection(
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
        cSupplied,
        cSupplied_whale,
        inverseGov,
        cSupply_amount,
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

    cSupplied.approve(strategy, 2 ** 256 - 1, {"from": inverseGov})

    # 10 yfi
    strategy.setCSupplied("0xde2af899040536884e062D3a334F2dD36F34b4a4", {"from": inverseGov})

    print("before injection")
    util.stateOfStrat(strategy, token)
    strategy.supplyCollateral(cSupply_amount, {"from": inverseGov})

    assert strategy.valueOfCSupplied() > 0

    print("after injection")
    util.stateOfStrat(strategy, token)
    # increase rewards, lending interest and borrowing interests
    # assets_before = vault.totalAssets()
    chain.sleep(30 * 24 * 3600)  # 30 days
    chain.mine(1)
    strategy.harvest()
    weth.transfer(
        delegatedVault, Wei("20 ether"), {"from": weth_whale}
    )  # simulate delegated vault interest

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
    print("before removed")
    util.stateOfStrat(strategy, token)

    strategy.removeCollateral(cSupply_amount, {"from": inverseGov})

    print("after removed")
    util.stateOfStrat(strategy, token)
    assert cSupplied.balanceOf(inverseGov) == cSupply_amount


def test_change_debt_with_injection(
        gov,
        token,
        vault,
        strategy,
        user,
        strategist,
        amount,
        RELATIVE_APPROX,
        cSupplied,
        cSupply_amount,
        inverseGov,
):
    cSupplied.approve(strategy, 2 ** 256 - 1, {"from": inverseGov})
    # 10 yfi
    strategy.setCSupplied("0xde2af899040536884e062D3a334F2dD36F34b4a4", {"from": inverseGov})

    print("before injection")
    util.stateOfStrat(strategy, token)
    strategy.supplyCollateral(cSupply_amount, {"from": inverseGov})

    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    strategy.setBorrowLimit(1000 * 10 ** 18)
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()

    print("debtRatio 5000")
    util.stateOfStrat(strategy, token)

    half = int(amount / 2)

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    vault.updateStrategyDebtRatio(strategy.address, 10_000, {"from": gov})
    strategy.harvest()

    print("debtRatio 10000")
    util.stateOfStrat(strategy, token)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # In order to pass this tests, you will need to implement prepareReturn.
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()

    print("debtRatio 5000")
    util.stateOfStrat(strategy, token)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half
