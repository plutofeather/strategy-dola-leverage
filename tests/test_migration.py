# TODO: Add tests that show proper migration of the strategy to a newer one
#       Use another copy of the strategy to simulate the migration
#       Show that nothing is lost!

import pytest
import util


# Migration for this strategy requires revoke

# def test_migration(
#         token, vault, strategy, amount, Strategy, strategist, gov, user, RELATIVE_APPROX, cWant, cBorrowed,
#         delegatedVault, chain, name
# ):

    # # Deposit to the vault and harvest
    # token.approve(vault.address, amount, {"from": user})
    # strategy.setBorrowLimit(1000 * 10 ** 18)
    # vault.deposit(amount, {"from": user})
    # util.stateOfVault(vault, strategy, token)
    #
    # strategy.harvest()
    # print(f'block {chain}')
    # util.stateOfStrat(strategy, token)
    # util.stateOfVault(vault, strategy, token)
    # assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    #
    # # migrate to a new strategy
    # new_strategy = strategist.deploy(Strategy, vault, cWant, cBorrowed, delegatedVault, name)
    # new_strategy.setBorrowLimit(1000 * 10 ** 18)
    # strategy.migrate(new_strategy.address, {"from": gov})
    # print(f'block {chain}')
    # util.stateOfStrat(new_strategy, token)
    # util.stateOfVault(vault, new_strategy, token)
    #
    # assert (
    #         pytest.approx(new_strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX)
    #         == amount
    # )

