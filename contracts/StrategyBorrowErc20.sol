// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import {BaseStrategy, VaultAPI} from "@yearnvaults/contracts/BaseStrategy.sol";
import {SafeERC20, SafeMath, IERC20, Address} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import {Math} from "@openzeppelin/contracts/math/Math.sol";


import "../interfaces/inverse.sol";
import "../interfaces/uniswap.sol";
import "../interfaces/weth.sol";

contract StrategyBorrowERC20 is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    modifier onlyInverseGovernance() {
        require(msg.sender == inverseGovernance);
        _;
    }

    uint private constant NO_ERROR = 0;

    IUniswapV2Router02 public router;
    VaultAPI public delegatedVault;

    ComptrollerInterface private comptroller;

    CErc20Interface public cWant;
    CEther public cBorrowed;
    CErc20Interface public cSupplied; // private market for Yearn, panDola
    xInvCoreInterface public xInv;

    IERC20 public borrowed;
    IERC20 public reward; // INV
    IWETH9 internal weth = IWETH9(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);

    address[] private borrowedWantPath;
    address[] private rewardWantPath;
    address[] private wethWantPath;
    address[] private wantWethPath;
    address[] private claimableMarkets;

    uint public minRedeemPrecision;
    string private strategyName;
    address public inverseGovernance;
    uint256 public collateralTolerance;
    uint256 public borrowLimit; // borrow nothing until set
    uint256 public percentRewardToSell; // sell nothing until set
    uint256 internal constant dustLowerBound = 0.01 ether; // threshold for paying off borrowed dust
    uint256 constant public max = type(uint256).max;

    constructor(address _vault, address _cWant, address _cBorrowed, address _delegatedVault, string memory _name) public BaseStrategy(_vault) {
        strategyName = _name;
        inverseGovernance = 0x926dF14a23BE491164dCF93f4c468A50ef659D5B; // Inverse Timelock

        delegatedVault = VaultAPI(_delegatedVault);
        router = IUniswapV2Router02(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D);

        cWant = CErc20Interface(_cWant);
        cBorrowed = CEther(_cBorrowed);
        xInv = xInvCoreInterface(0x65b35d6Eb7006e0e607BC54EB2dFD459923476fE);
        // TODO temporarily Sushibar
        cSupplied = CErc20Interface(0xD60B06B457bFf7fc38AC5E7eCE2b5ad16B288326);

        borrowed = IERC20(delegatedVault.token());
        reward = IERC20(0x41D5D79431A913C4aE7d69a668ecdfE5fF9DFB68);

        require(cWant.underlying() != address(borrowed));
        require(cWant.underlying() == address(want));
        require(address(cWant) != address(cBorrowed));
        require(address(cWant) != address(cSupplied));
        require(address(cWant) != address(xInv));
        require(address(cBorrowed) != address(cSupplied));
        require(address(cBorrowed) != address(xInv));
        require(address(cSupplied) != address(xInv));

        if (address(borrowed) == address(weth) || address(want) == address(weth)) {
            borrowedWantPath = [address(borrowed), address(want)];
        } else {
            borrowedWantPath = [address(borrowed), address(weth), address(want)];
        }

        rewardWantPath = [address(reward), address(weth), address(want)];
        wethWantPath = [address(weth), address(want)];
        wantWethPath = [address(want), address(weth)];

        claimableMarkets = [address(cWant), address(cBorrowed), address(cSupplied)];
        comptroller = ComptrollerInterface(cWant.comptroller());
        comptroller.enterMarkets(claimableMarkets);
        // 1%
        collateralTolerance = 0.01 ether;

        want.safeApprove(address(cWant), max);
        want.safeApprove(address(router), max);
        borrowed.safeApprove(address(delegatedVault), max);
        borrowed.approve(address(router), max);
        reward.approve(address(router), max);
        reward.approve(address(xInv), max);

        minRedeemPrecision = 10 ** vault.decimals().sub(cWant.decimals());

        // delegate voting power to yearn gov
        xInv.delegate(governance());
    }

    //
    // BaseContract overrides
    //

    function name() external view override returns (string memory) {
        return strategyName;
    }

    // User portion of the delegated assets in want
    function delegatedAssets() external override view returns (uint256) {
        uint256 _totalCollateral = valueOfTotalCollateral();
        if (_totalCollateral == 0) {
            return 0;
        }

        uint256 _userDelegated = valueOfDelegated().mul(valueOfCWant()).div(_totalCollateral);
        return _usdToBase(_userDelegated, cWant, false);
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        return balanceOfWant().add(_usdToBase(valueOfCWant().add(valueOfDelegated()).sub(valueOfBorrowedOwed()), cWant, false));
    }

    function prepareReturn(uint256 _debtOutstanding) internal override returns (uint256 _profit, uint256 _loss, uint256 _debtPayment){
        uint256 _looseBalance = balanceOfWant();
        _sellDelegatedProfits();
        _sellLendingProfits();

        comptroller.claimComp(address(this), claimableMarkets);
        if (percentRewardToSell > 0) {
            uint256 _rewardsToSell = balanceOfReward().mul(percentRewardToSell).div(100);
            if (_rewardsToSell > 1e9) {
                router.swapExactTokensForTokens(_rewardsToSell, 0, rewardWantPath, address(this), now);
            }
        }

        uint256 _balanceAfterProfit = balanceOfWant();
        if (_balanceAfterProfit > _looseBalance) {
            _profit = _balanceAfterProfit.sub(_looseBalance);
        }

        if (_debtOutstanding > 0) {
            uint256 _before = balanceOfWant();
            _loss = _redeem(_debtOutstanding);
            uint256 _after = balanceOfWant();
            _debtPayment = Math.min(_debtOutstanding, _after.sub(_before));
            if (_loss > 0) {
                _profit = 0;
            }
        }
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        assert(cWant.mint(balanceOfWant()) == NO_ERROR);
        assert(xInv.mint(balanceOfReward()) == NO_ERROR);

        _rebalance();
    }

    function liquidatePosition(uint256 _amountNeeded) internal override returns (uint256 _liquidatedAmount, uint256 _loss){
        uint256 _looseBalance = balanceOfWant();
        if (_amountNeeded > _looseBalance) {
            if (_amountNeeded == max) {
                _looseBalance = 0;
            }
            _loss = _redeem(_amountNeeded.sub(_looseBalance));
            _liquidatedAmount = Math.min(_amountNeeded, balanceOfWant());
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    function liquidateAllPositions() internal override returns (uint256 _amountFreed){
        (_amountFreed,) = liquidatePosition(max);
    }

    function tendTrigger(uint256 callCostInWei) public override virtual view returns (bool) {
        uint256 _valueCollateral = valueOfTotalCollateral();
        if (harvestTrigger(callCostInWei) || _valueCollateral == 0) {
            return false;
        }

        uint256 currentCF = valueOfBorrowedOwed().mul(1e18).div(_valueCollateral);
        return targetCollateralFactor().sub(collateralTolerance) > currentCF || currentCF > targetCollateralFactor().add(collateralTolerance);
    }

    function prepareMigration(address _newStrategy) internal override {
        // do nothing. Borrowed position can't be transferred so need to unwind everything before migrating
    }

    function protectedTokens() internal view override returns (address[] memory) {
        // Leave this empty.
    }

    function ethToWant(uint256 _amtInWei) public view override returns (uint256) {
        if (_amtInWei > 0) {
            return router.getAmountsOut(_amtInWei, wethWantPath)[1];
        }
    }

    receive() external payable {}


    //
    // Helpers
    //

    function targetCollateralFactor() public view returns (uint256) {
        (bool isListed, uint256 collateralFactorMantissa, bool isComped) = comptroller.markets(address(cBorrowed));
        return collateralFactorMantissa.sub(0.1 ether);
    }

    // repay borrowed position to free up collateral.
    function _freeUpCollateral(uint256 _usdCollatNeeded, bool force) internal {
        bool _needMax = _usdCollatNeeded == max;

        cBorrowed.accrueInterest();

        uint256 _usdCollatFree;
        if (!force) {
            _usdCollatFree = _usdCollateralFree();
        }
        if (_usdCollatNeeded > _usdCollatFree) {
            uint256 _usdMoreNeeded = _usdCollatNeeded.sub(_usdCollatFree);
            uint256 _usdBorrowToRepay = _needMax ? max : _usdMoreNeeded.mul(targetCollateralFactor()).div(1e18);
            uint256 _borrowed = _usdToBase(_usdBorrowToRepay, cBorrowed, false);
            uint256 _shares = Math.min(_borrowedToShares(_borrowed), delegatedVault.balanceOf(address(this)));

            uint256 _borrowedWithdrawn = delegatedVault.withdraw(_shares);

            weth.withdraw(_borrowedWithdrawn);
            cBorrowed.repayBorrow{value : balanceOfEth()}();

            uint256 _usdBorrowedRepaid = _usdToBase(_borrowedWithdrawn, cBorrowed, true);
            uint256 _usdCollatFreedUp = _usdBorrowedRepaid.mul(1e18).div(targetCollateralFactor());
            if (_usdCollatNeeded > _usdCollatFreedUp) {
                _usdMoreNeeded = _needMax ? max : _usdCollatNeeded.sub(_usdCollatFreedUp);
                _repayWithWant(_usdMoreNeeded, force);
            }
        }
    }

    // if unwinding delegatedVault was not enough (delegatedVault pps lowered, or market interest), start trading want -> eth to free up collateral
    function _repayWithWant(uint256 _usdMoreNeeded, bool force) internal {
        bool _needMax = _usdMoreNeeded == max;
        uint256 _usdCollatFree;
        if (!force) {
            _usdCollatFree = _usdCollateralFree();
        }
        if (_usdMoreNeeded > _usdCollatFree) {
            uint256 _usdToRepay = _needMax ? max : _usdMoreNeeded.sub(_usdCollatFree).mul(targetCollateralFactor()).div(1e18);
            uint256 _borrowedToRepay = _usdToBase(_usdToRepay, cBorrowed, false);


            uint256 _borrowedOwed = cBorrowed.borrowBalanceCurrent(address(this));
            uint256 _usdBorrowedOwed = _usdToBase(_borrowedOwed, cBorrowed, true);

            // if payment would leave borrowed dust or payment is lower than borrowed lower bound, pay everything
            if (dustLowerBound > _usdBorrowedOwed) {
                _borrowedToRepay = _borrowedOwed;
            } else {
                _borrowedToRepay = Math.min(_borrowedOwed, _borrowedToRepay);
            }

            // calculate exact want needed to repay borrowed
            if (_borrowedToRepay > 0) {
                uint256 _wantToRepay = router.getAmountsIn(_borrowedToRepay, wantWethPath)[0];

                if (_wantToRepay > minRedeemPrecision) {
                    cWant.accrueInterest();
                    _usdToRepay = _usdToBase(_wantToRepay, cWant, true);

                    // make sure we have enough cWant freed to do the redeem
                    if (_usdCollateralFree() > _usdToRepay && valueOfCWant() > _usdToRepay) {
                        cWant.redeemUnderlying(_wantToRepay);
                        router.swapTokensForExactTokens(_borrowedToRepay, balanceOfWant(), wantWethPath, address(this), now);
                        weth.withdraw(weth.balanceOf(address(this)));
                        cBorrowed.repayBorrow{value : balanceOfEth()}();
                    }
                }
            }
        }}

    function _usdCollateralFree() internal returns (uint256 _usdFree){
        uint256 _usdCollatToMaintain = valueOfBorrowedOwed().mul(1e18).div(targetCollateralFactor());
        uint256 _usdTotalCollat = valueOfTotalCollateral();
        if (_usdTotalCollat > _usdCollatToMaintain) {
            _usdFree = _usdTotalCollat.sub(_usdCollatToMaintain);
        }
    }

    function _redeem(uint256 _wantNeeded) internal returns (uint256 _wantShort){
        _freeUpCollateral(_usdToBase(_wantNeeded, cWant, true), false);

        uint256 _wantAllowed = _usdToBase(_usdCollateralFree(), cWant, false);
        uint256 _wantCash = cWant.getCash();
        uint256 _wantHeld = balanceOfBase(cWant);

        uint256 _wantRedeemable = Math.min(Math.min(Math.min(_wantNeeded, _wantCash), _wantHeld), _wantAllowed);
        if (_wantRedeemable > minRedeemPrecision) {
            require(cWant.redeemUnderlying(_wantRedeemable) == NO_ERROR);
        }

        uint256 _wantAfter = balanceOfWant();
        if (_wantNeeded > _wantAfter && _wantNeeded != max) {
            _wantShort = _wantNeeded.sub(_wantAfter);
        }
    }


    // Calculate adjustments on borrowing market to maintain healthy targetCollateralFactor and borrowLimit
    function _calculateUsdBorrowAdjustment() internal returns (uint256 _usdAdjustment, bool _neg){
        uint256 _usdTotalCollat = valueOfTotalCollateral();
        _usdTotalCollat = _usdTotalCollat > dustLowerBound ? _usdTotalCollat : 0;
        uint256 _usdBorrowTarget = _usdTotalCollat.mul(targetCollateralFactor()).div(1e18);

        // enforce borrow limit
        uint256 _usdBorrowLimit = _usdToBase(borrowLimit, cBorrowed, true);
        if (_usdBorrowTarget > _usdBorrowLimit) {
            _usdBorrowTarget = _usdBorrowLimit;
        }

        uint256 _usdBorrowOwed = valueOfBorrowedOwed();
        if (_usdBorrowOwed > _usdBorrowTarget) {
            _neg = true;
            _usdAdjustment = _usdBorrowOwed.sub(_usdBorrowTarget);
        } else {
            _usdAdjustment = _usdBorrowTarget.sub(_usdBorrowOwed);
        }
    }


    function _rebalance() internal {
        cBorrowed.accrueInterest();
        (uint256 _usdBorrowAdjustment, bool _neg) = _calculateUsdBorrowAdjustment();
        if (_neg) {
            // undercollateralized, must unwind and repay to free up collateral
            uint256 _usdCollatToFree = _usdBorrowAdjustment.mul(1e18).div(targetCollateralFactor());
            _freeUpCollateral(_usdCollatToFree, true);
        } else if (_usdBorrowAdjustment > 0) {
            // overcollateralized, can borrow more
            uint256 _borrowedAdjustment = Math.min(_usdToBase(_usdBorrowAdjustment, cBorrowed, false), cBorrowed.getCash());
            assert(cBorrowed.borrow(_borrowedAdjustment) == NO_ERROR);
            uint256 _borrowedActual = address(this).balance;
            weth.deposit{value : _borrowedActual}();
            uint256 _wethBalance = weth.balanceOf(address(this));
            delegatedVault.deposit(_wethBalance);
        }
    }

    // sell profits earned from delegated vault
    function _sellDelegatedProfits() internal {
        cBorrowed.accrueInterest();
        uint256 _valueOfBorrowed = valueOfBorrowedOwed();
        uint256 _valueOfDelegated = valueOfDelegated();

        if (_valueOfDelegated > _valueOfBorrowed) {
            uint256 _valueOfProfit = _valueOfDelegated.sub(_valueOfBorrowed);
            uint256 _amountInShares = _borrowedToShares(_usdToBase(_valueOfProfit, cBorrowed, false));
            if (_amountInShares >= delegatedVault.balanceOf(address(this))) {
                // max uint256 is uniquely set to withdraw everything
                _amountInShares = max;
            }
            uint256 _actualWithdrawn = delegatedVault.withdraw(_amountInShares);
            // sell to want
            if (_actualWithdrawn > 0) {
                router.swapExactTokensForTokens(_actualWithdrawn, 0, borrowedWantPath, address(this), now);
            }
        }
    }

    function _sellLendingProfits() internal {
        cWant.accrueInterest();
        uint256 _debt = vault.strategies(address(this)).totalDebt;
        uint256 _totalAssets = balanceOfBase(cWant);

        if (_totalAssets > _debt) {
            _redeem(_totalAssets.sub(_debt));
        }
    }

    // Loose want
    function balanceOfWant() public view returns (uint256) {
        return want.balanceOf(address(this));
    }

    function balanceOfReward() public view returns (uint256){
        return reward.balanceOf(address(this));
    }

    function balanceOfEth() public view returns (uint256){
        return address(this).balance;
    }

    function balanceOfBase(CTokenInterface cToken) internal view returns (uint256){
        return _cToBase(cToken.balanceOf(address(this)), cToken);
    }

    // Value of deposited want in USD
    function valueOfCWant() public view returns (uint256){
        return _usdToBase(balanceOfBase(cWant), cWant, true);
    }

    // Value of Inverse supplied tokens in USD
    function valueOfCSupplied() public view returns (uint256){
        return _usdToBase(balanceOfBase(cSupplied), cSupplied, true);
    }

    // Value of reward tokens in USD
    function valueOfxInv() public view returns (uint256){
        return _usdToBase(balanceOfBase(xInv), xInv, true);
    }

    function valueOfTotalCollateral() public view returns (uint256){
        return valueOfCWant().add(valueOfCSupplied()).add(valueOfxInv());
    }

    // Value of borrowed tokens in USD
    function valueOfBorrowedOwed() public view returns (uint256){
        return _usdToBase(cBorrowed.borrowBalanceStored(address(this)), cBorrowed, true);
    }

    // Value of delegated vault deposits in USD
    function valueOfDelegated() public view returns (uint256){
        uint256 _amountInBorrowed = delegatedVault.balanceOf(address(this)).mul(delegatedVault.pricePerShare()).div(10 ** delegatedVault.decimals());
        return _usdToBase(_amountInBorrowed, cBorrowed, true);
    }

    function _usdToBase(uint256 _amount, CTokenInterface cToken, bool reverse) internal view returns (uint256){
        if (_amount == max || _amount == 0) return _amount;
        uint256 _usdPerUnderlying = comptroller.oracle().getUnderlyingPrice(address(cToken));
        if (reverse) {
            return _amount.mul(_usdPerUnderlying).div(1e18);
        } else {
            return _amount.mul(1e18).div(_usdPerUnderlying);
        }
    }

    function _borrowedToShares(uint256 _amountBorrowed) internal view returns (uint256){
        if (_amountBorrowed == max || _amountBorrowed == 0) return _amountBorrowed;
        uint256 _borrowedPerShare = delegatedVault.pricePerShare();
        return _amountBorrowed.mul(10 ** delegatedVault.decimals()).div(_borrowedPerShare);
    }

    function _cToBase(uint256 _amountCToken, CTokenInterface cToken) internal view returns (uint256){
        if (_amountCToken == max || _amountCToken == 0) return _amountCToken;
        uint256 _underlyingPerCToken = cToken.exchangeRateStored();
        return _amountCToken.mul(_underlyingPerCToken).div(1e18);
    }

    function redeemRewards(uint256 _amount) external onlyAuthorized {
        xInv.redeem(_amount);
    }
    // used after a migration to redeem escrowed INV tokens that can then be swept by gov
    function withdrawEscrowedRewards() external onlyAuthorized {
        TimelockEscrowInterface _timelockEscrow = TimelockEscrowInterface(xInv.escrow());
        _timelockEscrow.withdraw();
    }


    //
    // Setters
    //

    function setRouter(address _address) external onlyGovernance {
        // want.safeApprove(address(router), 0);
        // borrowed.approve(address(router), 0);
        // reward.approve(address(router), 0);

        router = IUniswapV2Router02(_address);
        want.safeApprove(address(router), max);
        borrowed.approve(address(router), max);
        reward.approve(address(router), max);
    }

    function setComptroller() external onlyAuthorized {
        comptroller = ComptrollerInterface(cWant.comptroller());
        comptroller.enterMarkets(claimableMarkets);
    }

    function setCollateralTolerance(uint256 _toleranceMantissa) external onlyGovernance {
        collateralTolerance = _toleranceMantissa;
    }

    function setInvDelegate(address _address) external onlyGovernance {
        xInv.delegate(_address);
    }

    function setBorrowLimit(uint256 _borrowLimit) external onlyAuthorized {
        borrowLimit = _borrowLimit;
    }

    function setPercentRewardToSell(uint256 _percentRewardToSell) external onlyAuthorized {
        require(_percentRewardToSell <= 100);
        percentRewardToSell = _percentRewardToSell;
    }

    //
    // For Inverse Finance
    //

    function setInverseGovernance(address _inverseGovernance) external onlyInverseGovernance {
        inverseGovernance = _inverseGovernance;
    }

    function setCSupplied(address _address) external onlyInverseGovernance {
        require(_address != address(cWant));

        comptroller.exitMarket(address(cSupplied));
        cSupplied = CErc20Interface(address(_address));

        claimableMarkets[2] = _address;
        comptroller.enterMarkets(claimableMarkets);
    }

    // @param _amount in cToken from the private market
    function supplyCollateral(uint256 _amount) external onlyInverseGovernance returns (bool) {
        return cSupplied.transferFrom(msg.sender, address(this), _amount);
    }

    function removeCollateral(uint256 _cTokenAmount) external onlyInverseGovernance {
        _freeUpCollateral(_usdToBase(_cToBase(_cTokenAmount, cSupplied), cSupplied, true), false);
        cSupplied.transfer(msg.sender, Math.min(_cTokenAmount, cSupplied.balanceOf(address(this))));
    }
}
