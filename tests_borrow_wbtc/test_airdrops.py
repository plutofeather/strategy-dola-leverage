import brownie
import pytest
import util
from brownie import Contract, Wei

def test_airdrop_want(
        cWant,
        chain,
        accounts,
        token,
        vault,
        strategy,
        user,
        strategist,
        token_whale,
        amount,
        RELATIVE_APPROX,
        delegatedVault,
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    strategy.setBorrowLimit(1000 * 1e18)
    token.approve(vault, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault) == amount

    # harvest
    strategy.harvest({"from": strategist})
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount


    print("==== Airdrop ====")
    airdrop_amount = 500 * 1e18
    starting_total_assets = strategy.estimatedTotalAssets()
    token.transfer(strategy, airdrop_amount, {"from": token_whale})
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)
    assert token.balanceOf(strategy) == airdrop_amount
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == starting_total_assets + airdrop_amount

    print("==== Tend ====")
    strategy.tend({"from": strategist})
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)
    assert token.balanceOf(strategy) == 0

    print("==== Harvest ====")
    strategy.harvest({"from": strategist})
    chain.sleep(3600 * 7)  # 6 hrs for pps to recover
    chain.mine(1)
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)

    print("==== Withdraw ====")
    vault.withdraw({"from": user})
    user_balance_after = token.balanceOf(user)
    print("gain: ", (user_balance_after - user_balance_before) / 1e18)
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)
    assert user_balance_after > user_balance_before


def test_airdrop_cwant(
        cWant,
        chain,
        accounts,
        token,
        vault,
        strategy,
        user,
        strategist,
        cwant_whale,
        amount,
        RELATIVE_APPROX,
        delegatedVault,
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    strategy.setBorrowLimit(1000 * 1e8)
    token.approve(vault, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault) == amount

    # harvest
    strategy.harvest({"from": strategist})
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    print("==== Airdrop ====")
    airdrop_amount = 500 * 1e8
    starting_cwant_balance = cWant.balanceOf(strategy)
    starting_total_assets = strategy.estimatedTotalAssets()
    cWant.transfer(strategy, airdrop_amount, {"from": cwant_whale})
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)
    assert cWant.balanceOf(strategy) - starting_cwant_balance == airdrop_amount

    print("==== Tend ====")
    strategy.tend({"from": strategist})
    assert token.balanceOf(strategy) == 0
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)

    print("==== Harvest ====")
    strategy.harvest({"from": strategist})
    chain.sleep(3600 * 7)  # 6 hrs for pps to recover
    chain.mine(1)
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)

    print("==== Withdraw ====")
    vault.withdraw({"from": user})
    user_balance_after = token.balanceOf(user)
    assert user_balance_after > user_balance_before
    print("gain: ", (user_balance_after - user_balance_before) / 1e18)
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)

def test_airdrop_borrowed(
        cWant,
        chain,
        accounts,
        token,
        weth,
        vault,
        strategy,
        user,
        strategist,
        weth_whale,
        amount,
        RELATIVE_APPROX,
        delegatedVault,
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    strategy.setBorrowLimit(1000 * 1e18)
    token.approve(vault, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault) == amount

    # harvest
    strategy.harvest({"from": strategist})
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount


    print("==== Airdrop ====")
    airdrop_amount = 500 * 1e18
    starting_total_assets = strategy.estimatedTotalAssets()
    weth.transfer(strategy, airdrop_amount, {"from": weth_whale})
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)
    assert weth.balanceOf(strategy) == airdrop_amount

    print("==== Tend ====")
    strategy.tend({"from": strategist})
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)
    assert weth.balanceOf(strategy) == airdrop_amount

    print("==== Harvest ====")
    # 1st harvest puts weth in delegated vault
    strategy.harvest({"from": strategist})
    assert weth.balanceOf(strategy) == 0
    chain.sleep(3600 * 7)  # 6 hrs for pps to recover
    chain.mine(1)

    # 2nd harvest is when strat will calculate it as profit
    strategy.harvest({"from": strategist})
    chain.sleep(3600 * 7)  # 6 hrs for pps to recover
    chain.mine(1)

    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)

    print("==== Withdraw ====")
    vault.withdraw({"from": user})
    user_balance_after = token.balanceOf(user)
    assert user_balance_after > user_balance_before
    print("gain: ", (user_balance_after - user_balance_before) / 1e18)
    util.stateOfStrat(strategy, token)
    util.stateOfVault(vault, strategy, token)
