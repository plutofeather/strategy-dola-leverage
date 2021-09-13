import pytest
from brownie import Contract, config


@pytest.fixture
def gov(accounts):
    yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)


@pytest.fixture
def user(accounts):
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


@pytest.fixture
def token(interface):
    token_address = "0x865377367054516e17014ccded1e7d814edc9ce4"  # DOLA
    yield interface.ERC20(token_address)


@pytest.fixture
def token_whale(accounts):
    yield accounts.at("0x9547429C0e2c3A8B88C6833B58FCE962734C0E8C", force=True)  # DOLA 3CRV Curve Metapool

@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

@pytest.fixture
def amount(accounts, token, user, token_whale):
    amount = 100000 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    token.transfer(user, amount, {"from": token_whale})
    yield amount


@pytest.fixture
def weth():
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    yield Contract(token_address)


@pytest.fixture
def weth_whale(accounts):
    yield accounts.at("0x2F0b23f53734252Bda2277357e97e1517d6B042A", force=True)


@pytest.fixture
def weth_amout(user, weth):
    weth_amout = 10 ** weth.decimals()
    user.transfer(weth, weth_amout)
    yield weth_amout


@pytest.fixture
def name():
    return "StrategyDolaEthLeverage"


@pytest.fixture
def vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(token, gov, rewards, "", "", guardian, {"from": gov})
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    vault.setManagementFee(0, {"from": gov})
    vault.setPerformanceFee(0, {"from": gov})
    yield vault


@pytest.fixture
def strategy(strategist, keeper, vault, Strategy, gov, cWant, cBorrowed, delegatedVault, cSupplied, name):
    strategy = strategist.deploy(Strategy, vault, cWant, cBorrowed, delegatedVault, name)
    strategy.setKeeper(keeper, {"from": strategist})
    strategy.setMaxReportDelay(86400, {"from": strategist})  # 1 day
    strategy.setDebtThreshold(100000 * 1e18, {"from": strategist})
    strategy.setPercentRewardToSell(10, {"from": strategist})
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    yield strategy


@pytest.fixture
def cWant():
    token_address = "0x7fcb7dac61ee35b3d4a51117a7c58d53f0a8a670"  # anDOLA
    yield Contract(token_address)


@pytest.fixture
def cwant_whale(accounts):
    yield accounts.at("0x5E075E40D01c82B6Bf0B0ecdb4Eb1D6984357EF7", force=True)  # Fed


@pytest.fixture
def cSupplied():
    token_address = "0xde2af899040536884e062D3a334F2dD36F34b4a4"  # temporarily anYFI
    yield Contract(token_address)


@pytest.fixture
def cSupplied_whale(accounts):
    token_address = "0x7BFEe91193d9Df2Ac0bFe90191D40F23c773C060"
    yield accounts.at(token_address, force=True)


@pytest.fixture
def cBorrowed():
    token_address = "0x697b4acAa24430F254224eB794d2a85ba1Fa1FB8"  # anETH
    yield Contract(token_address)


@pytest.fixture
def inv():
    yield Contract("0x41d5d79431a913c4ae7d69a668ecdfe5ff9dfb68")


@pytest.fixture
def inv_whale(accounts):
    yield accounts.at("0x926dF14a23BE491164dCF93f4c468A50ef659D5B", force=True)  # Inverse Timelock


@pytest.fixture
def rook():
    token_address = "0xfA5047c9c78B8877af97BDcb85Db743fD7313d4a"
    yield Contract(token_address)


@pytest.fixture
def rook_whale(accounts):
    yield accounts.at("0xb81f5b9bd373b9d0df2e3191a01b8fa9b4d2832a", force=True)


@pytest.fixture
def delegatedVault():
    token_address = "0xa9fE4601811213c340e850ea305481afF02f5b28"  # WETH yVault
    yield Contract(token_address)


@pytest.fixture
def inverseGov(cSupplied_whale, cSupplied, cSupply_amount):
    token_address = "0x926dF14a23BE491164dCF93f4c468A50ef659D5B" # Inverse timelock
    invGov = Contract(token_address)
    cSupplied.transfer(invGov, cSupply_amount, {"from": cSupplied_whale})
    yield invGov


@pytest.fixture
def cSupply_amount(cSupplied):
    yield 10 * 10 ** cSupplied.decimals()


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-3
