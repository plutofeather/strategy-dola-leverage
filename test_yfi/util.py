

def stateOfStrat(strategy, token):
    print('\n-----State of Strat-----')
    print('targetCF : ', strategy.targetCollateralFactor()/1e18)
    print('balanceOfWant : ', strategy.balanceOfWant())
    print('balanceOfReward: ', strategy.balanceOfReward())
    print('balanceOfEth: ', strategy.balanceOfEth())
    print('valueOfCWant: ', strategy.valueOfCWant()/1e18)
    print('valueOfCSupplied (usd): ', strategy.valueOfCSupplied()/1e18)
    print('valueOfxInv (usd): ', strategy.valueOfxInv()/1e18)
    print('valueOfTotalCollateral (usd): ', strategy.valueOfTotalCollateral()/1e18)
    print('valueOfBorrowedOwed (usd): ', strategy.valueOfBorrowedOwed()/1e18)
    print('valueOfDelegated (usd): ', strategy.valueOfDelegated()/1e18)
    print('estimatedTotalAssets (want): ', strategy.estimatedTotalAssets()/10**token.decimals())
    print('delegatedAssets (want): ', strategy.delegatedAssets()/10**token.decimals())
    print('\n')

def stateOfVault(vault, strategy, token):
    vaultAssets = vault.totalAssets()/1e18
    vaultDebt = vault.totalDebt()/1e18
    vaultLoose = token.balanceOf(vault)/1e18
    vaultPps = vault.pricePerShare()/1e18

    strState = vault.strategies(strategy)
    stratDebt = strState[6]/1e18
    stratReturns = strState[7]/1e18
    stratLosses = strState[8]/1e18

    print('\n-----State of Vault-----')
    print(f"Vault assets: {vaultAssets:.5f}")
    print(f"Vault debt: {vaultDebt:.5f}")
    print(f"Vault loose balance: {vaultLoose:.5f}")
    print(f"Vault PPS: {vaultPps:.5f}")
    print(f"Strategy Debt: {stratDebt:.5f}")
    print(f"Strategy Returns: {stratReturns:.5f}")
    print(f"Strategy Losses: {stratLosses:.5f}")
    print('\n')