import pytest
import util

def test_revoke_strategy_from_vault(
        token, vault, strategy, amount, user, gov, RELATIVE_APPROX
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    print(f"\n before harvest")
    util.stateOfStrat(strategy, token)

    util.stateOfVault(vault, strategy, token)

    # In order to pass this tests, you will need to implement prepareReturn.
    # TODO: uncomment the following lines.
    vault.revokeStrategy(strategy.address, {"from": gov})
    strategy.harvest()
    print(f"\n after harvest")
    util.stateOfStrat(strategy, token)

    util.stateOfVault(vault, strategy, token)

    assert pytest.approx(token.balanceOf(vault.address), rel=RELATIVE_APPROX) == amount


def test_revoke_strategy_from_strategy(
        token, vault, strategy, amount, gov, user, RELATIVE_APPROX
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    print(f"\n before harvest")
    util.stateOfStrat(strategy, token)

    util.stateOfVault(vault, strategy, token)

    strategy.setEmergencyExit()
    strategy.harvest()
    print(f"\n after harvest")
    util.stateOfStrat(strategy, token)

    util.stateOfVault(vault, strategy, token)

    assert pytest.approx(token.balanceOf(vault.address), rel=RELATIVE_APPROX) == amount

def test_emergency_exit(
        accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, chain
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    strategy.setBorrowLimit(100 * 1e18)
    print(f"vault pps: {vault.pricePerShare() / 1e18}")
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    util.stateOfVault(vault, strategy, token)

    chain.sleep(3600 * 6)  # 6 hrs for pps to recover
    chain.mine(1)

    # set emergency and exit
    strategy.setEmergencyExit({"from": strategist})
    print(f"\n before harvest")
    print(f"vault pps: {vault.pricePerShare()}")
    util.stateOfStrat(strategy, token)
    strategy.harvest({"from": strategist})
    print(f"\n after harvest")
    print(f"vault pps: {vault.pricePerShare()}")
    util.stateOfStrat(strategy, token)
    # dust
    assert strategy.estimatedTotalAssets() < 1e16

    util.stateOfVault(vault, strategy, token)

