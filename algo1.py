import asyncio
import math
import os

from tkinter import Canvas

from PyQt5.QtCore import QSize
import datetime as dt
import time
import pandas as pd
import logging
import numpy as np
import statistics
from statistics import stdev
import PyQt5.QtWidgets as qt

from PyQt5 import QtCore
from PyQt5 import QtWidgets
from ib_insync import IB, util, MarketOrder
from ib_insync.order import (
    BracketOrder, LimitOrder, Order, OrderState, OrderStatus, StopOrder, Trade)
from ib_insync.objects import AccountValue, TradeLogEntry
from ib_insync.contract import *  # noqa
from ib_insync.order import (
    BracketOrder, LimitOrder, Order, OrderState, OrderStatus, StopOrder, Trade)
from ib_insync.util import dataclassRepr, isNan
from typing import ClassVar, List, Optional, Union
from datetime import datetime
from eventkit import Event, Op
from matplotlib.figure import Figure
from maCalculator import MovAvgCalculator

nan = float('nan')
logfilename = os.path.join(os.getcwd(), "logs", datetime.now().strftime("%Y%m%d-%H%M%S"))
logfilename += '.txt'
logging.basicConfig(filename=logfilename,format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                    datefmt='%Y-%m-%d:%H:%M:%S',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)


def lowerHundred(number):
    return int(math.floor(number / 100.0)) * 100

#order object containing all order details of parent and TP/SL orders
class OrderObject():
    def __init__(self, ib, symbol: str = '', qty: float = 0, qDone: float = 0, price: float = 0, pOrder: Order = None, pOrderID: int = 0, tpOrderID: int = 0, slOrderID: int = 0):
        self.ib = ib
        self.symbol = symbol
        self.qty = qty
        self.qDone = qDone
        self.price = price
        self.pOrder = pOrder
        self.pOrderID = pOrderID
        self.pSide = ''
        self.pStatus = ''
        self.tpStatus = ''
        self.slStatus = ''
        self.tpOrderID = tpOrderID
        self.slOrderID = slOrderID
        self.orderStatus = []

    def setStatus(self, orderId: int = 0, status: str = ''):
        self.orderStatus[orderId] = status


class MovingAverages():
    def __init__(self, ib, ma20Array: np.array([]), symbol: str = '', maMinor: np.double = 0, ma20: np.double = '',
                 maMajor: np.double = ''):  # , reqId: float = 0):#, ma50: float = 0, ma200: float = 0):
        self.ib = ib
        self.symbol = symbol
        self.maMinor = maMinor
        self.ma20 = ma20
        self.maMajor = maMajor
        self.ma20Array = ma20Array
        self.prev_maMinor = 0
        self.prev_maMajor = 0
        self.prevPrice = self.prevClose = self.currPrice = 0
        self.priceCrossedBelowmaMinor = False
        self.priceCrossedBelowmaMajor = False
        self.priceCrossedAbovemaMinor = False
        self.priceCrossedAbovemaMajor = False
        self.bought = self.sold = False
        self.firstBar = True
        self.orderObj = OrderObject(ib, symbol)

    def setmaMinor(self, maMinorval):
        self.maMinor = maMinorval


    def setmaMajor(self, maMajorval):
        self.maMajor = maMajorval

    def getmaMinor(self) -> MovAvgCalculator:
        return self.maMinor

    def getmaMajor(self) -> MovAvgCalculator:
        return self.maMajor

    #calculates bollinger width
    def getBBWidth(self):
        print(self.ma20Array)
        sd20 = np.std(self.ma20Array)
        print("sd20 and ma20 " + str(sd20) + " " + str(self.ma20) )
        upperBand = self.ma20 + (sd20 * 2)
        lowerBand = self.ma20 - (sd20 * 2)
        return (upperBand - lowerBand)


#main class
class Window(qt.QWidget):
    def __init__(self, host, port, clientId):
        qt.QWidget.__init__(self)
        self.setWindowTitle("MA App")
        #self.logger = Logger()
        self.symbolInput = qt.QLineEdit("IBM")
        self.symbolInput.setFixedWidth(100)
        #self.typeInput = qt.QLineEdit(placeholderText="Stock")
        self.typeInput = qt.QLineEdit("Stock")
        self.typeInput.setFixedWidth(100)
        self.currencyInput = qt.QLineEdit("USD")
        self.currencyInput.setFixedWidth(100)
        self.exchangeInput = qt.QLineEdit("SMART")
        self.exchangeInput.setFixedWidth(100)
        self.dateInput = qt.QLineEdit("2")
        self.strikeInput = qt.QLineEdit()
        self.strikeInput.setFixedWidth(100)
        self.rightInput = qt.QLineEdit()
        self.rightInput.setFixedWidth(100)
        self.stopProfitInput = qt.QLineEdit("0.38")
        self.stopProfitInput.setFixedWidth(100)
        self.stopLossInput = qt.QLineEdit("-0.10")
        self.stopLossInput.setFixedWidth(100)
        self.BBWInput = qt.QLineEdit("0.0059")
        self.BBWInput.setFixedWidth(100)
        self.wma1Val = 10
        self.wma2Val = 50
        self.wma1Input = qt.QLineEdit("10")
        self.wma1Input.setFixedWidth(100)
        self.wma2Input = qt.QLineEdit("50")
        self.wma2Input.setFixedWidth(100)
        self.splittingCapitalInput = qt.QLineEdit("3")
        self.splittingCapitalInput.setFixedWidth(100)
        self.maxSignalPriceInput = qt.QLineEdit("0.05")
        self.maxSignalPriceInput.setFixedWidth(100)
        self.maxOpenPosInput = qt.QLineEdit("3")
        self.maxOpenPosInput.setFixedWidth(100)
        self.invAmountInput = qt.QLineEdit("10000")
        self.invAmountInput.setFixedWidth(100)
        self.connectButton = qt.QPushButton('Connect')
        self.connectButton.setFixedWidth(100)
        self.connectButton.clicked.connect(self.onConnectButtonClicked)
        self.displayButton = qt.QPushButton('Display values')
        self.displayButton.setFixedWidth(100)
        self.displayButton.clicked.connect(self.onDisplayButtonClicked)
        self.reqDataButton = qt.QPushButton('ReqData')
        self.reqDataButton.setFixedWidth(100)
        self.reqDataButton.clicked.connect(self.onReqDataButtonClicked)
        self.closePosButton = qt.QPushButton('Close Postions')
        self.closePosButton.setFixedWidth(100)
        self.closePosButton.clicked.connect(self.onClosePosButtonClicked)
        self.cancelAllButton = qt.QPushButton('CancelAll')
        self.cancelAllButton.setFixedWidth(100)
        self.cancelAllButton.clicked.connect(self.onCancelAllButtonClicked)
        outerLayout = qt.QVBoxLayout(self)
        layout0 = qt.QGridLayout(self)  # qt.QFormLayout(self)
        layout0.addWidget(self.connectButton, 0, 0)  # , alignment=QtCore.Qt.AlignCenter)
        layout0.addWidget(self.reqDataButton, 0, 1)  # , alignment=QtCore.Qt.AlignCenter)
        layout0.addWidget(self.cancelAllButton, 0, 2)  # , alignment=QtCore.Qt.AlignCenter)
        layout0.addWidget(self.closePosButton, 0, 3)  # , alignment=QtCore.Qt.AlignCenter)

        layout = qt.QGridLayout(self)#qt.QFormLayout(self)
        lSymbol = qt.QLabel("Symbol")
        lSymbol.setFixedSize(50, 10)
        lType = qt.QLabel("Type")
        lType.setFixedSize(50, 10)
        lDate = qt.QLabel("Exp Date")
        lDate.setFixedSize(50, 10)
        lStrike = qt.QLabel("Strike")
        lStrike.setFixedSize(50, 10)
        lRight = qt.QLabel("Right")
        lRight.setFixedSize(50, 10)
        lCurrency = qt.QLabel("Currency")
        lCurrency.setFixedSize(50, 10)
        lExchange = qt.QLabel("Exchange")
        lExchange.setFixedSize(50, 10)
        lStopProfit = qt.QLabel("Stop Profit")
        lStopProfit.setFixedSize(50, 10)
        lStopLoss = qt.QLabel("Stop Loss")
        lStopLoss.setFixedSize(50, 10)
        lBBW = qt.QLabel("BBWidth")
        lBBW.setFixedSize(50, 10)
        lWMA1 = qt.QLabel("WMA1")
        lWMA1.setFixedSize(50, 10)
        lWMA2 = qt.QLabel("WMA2")
        lWMA2.setFixedSize(50, 10)
        lSplittingCapital = qt.QLabel("SpltCapital")
        lSplittingCapital.setFixedSize(50, 10)
        lMaxSignalPrice = qt.QLabel("MaxSigPrice")
        lMaxSignalPrice.setFixedSize(60, 10)
        lMaxNoOpenPos = qt.QLabel("MaxOpenPos")
        lMaxNoOpenPos.setFixedSize(65, 10)
        lAmountInvested = qt.QLabel("AmountInv")
        lAmountInvested.setFixedSize(60, 10)
        """layout.addRow(lSymbol, self.symbolInput)
        layout.addRow(lType, self.typeInput)
        layout.addRow(lCurrency, self.currencyInput)
        layout.addRow(lExchange, self.exchangeInput)
        layout.addRow(lStopProfit, self.stopProfitInput)
        layout.addRow(lStopLoss, self.stopLossInput)
        layout.addRow(lBBW, self.BBWInput)
        layout.addRow(lWMA1, self.wma1Input)
        layout.addRow(lWMA2, self.wma2Input)
        layout.addRow(lSplittingCapital, self.splittingCapitalInput)
        layout.addRow(lMaxSignalPrice, self.maxSignalPrice)
        layout.addRow(lMaxNoOpenPos, self.maxOpenPos)
        layout.addRow(lAmountInvested, self.invAmount)"""


        layout.addWidget(lSymbol, 0, 0)
        layout.addWidget(self.symbolInput, 0, 1)
        layout.addWidget(lType, 0, 2)
        layout.addWidget(self.typeInput, 0, 3)
        layout.addWidget(lCurrency, 0, 4)
        layout.addWidget(self.currencyInput, 0, 5)
        layout.addWidget(lExchange, 0, 6)
        layout.addWidget(self.exchangeInput, 0, 7)
        layout.addWidget(lStopProfit, 0, 8)
        layout.addWidget(self.stopProfitInput, 0, 9)
        layout.addWidget(lStopLoss, 0, 10)
        layout.addWidget(self.stopLossInput, 0, 11)
        layout.addWidget(lBBW, 1, 0)
        layout.addWidget(self.BBWInput, 1, 1)
        layout.addWidget(lWMA1, 1, 2)
        layout.addWidget(self.wma1Input, 1, 3)
        layout.addWidget(lWMA2, 1, 4)
        layout.addWidget(self.wma2Input, 1, 5)
        layout.addWidget(lSplittingCapital, 1, 6)
        layout.addWidget(self.splittingCapitalInput, 1, 7)
        layout.addWidget(lMaxSignalPrice, 1, 8)
        layout.addWidget(self.maxSignalPriceInput, 1, 9)
        layout.addWidget(lMaxNoOpenPos, 1, 10)
        layout.addWidget(self.maxOpenPosInput, 1, 11)
        layout.addWidget(lAmountInvested, 2, 0)
        layout.addWidget(self.invAmountInput, 2, 1)
        #blayout = qt.QHBoxLayout(self)
        #blayout = qt.QGridLayout(self)
        #outerLayout.addLayout(blayout)
        outerLayout.addLayout(layout0)
        outerLayout.addLayout(layout)

        """layout1 = qt.QGridLayout(self)
        test1 = qt.QLabel("1")
        test2 = qt.QLabel("2")
        test3 = qt.QLabel("3")
        test1.setFixedSize(50, 10)
        test2.setFixedSize(50, 10)
        test3.setFixedSize(50, 10)
        layout1.addWidget(test1, 0, 0)
        layout1.addWidget(self.wma1Input, 0, 1)
        layout1.addWidget(test2, 0, 2)
        layout1.addWidget(self.wma2Input, 0, 3)
        layout1.addWidget(test3, 0, 4)
        layout1.addWidget(self.wma2Input, 0, 5)
        outerLayout.addLayout(layout1)"""

        self.table = qt.QTableWidget(self)
        self.table.setColumnCount(6)

        self.table.rowCount()
        # set table header
        self.table.setHorizontalHeaderLabels(['Symbol', 'WMA { }', 'WMA { }', 'Side', 'Position', 'Price'])
        vbox = qt.QVBoxLayout()
        vbox.addWidget(self.table)
        outerLayout.addLayout(vbox)

        self.setLayout(outerLayout)
        self.MAList = []
        self.MADict = {}
        self.rowDict = {}
        self.reqDict = []
        self.xs = []
        self.ys = []
        self.barData = {}
        # layout.addWidget(self.fig)
        self.connectInfo = (host, port, clientId)
        self.ib = IB()
        self.headers = [
            'symbol', 'bidSize', 'bid', 'ask', 'askSize',
            'last', 'lastSize', 'close']
        self.symdf = pd.DataFrame(columns=['symbol', 'bid', 'ask' , 'last'])
        self.id = 1;
        self.firstSignal = True
        self.isConnectionBroken = False
        self.closePos = False
        self.totalPos = 0
        self.firstmaMajor = 0
        self.firstma200 = 0
        self.availableCash = 10000

        #declaring the callbacks
        self.ib.positionEvent += self.position_cb
        self.ib.orderStatusEvent += self.order_status_cb
        self.ib.execDetailsEvent += self.exec_details_cb
        self.ib.errorEvent += self.error_cb
        self.ib.accountSummaryEvent += self.accountSummary
        self.ib.pendingTickersEvent += self.onPendingTickers #this callback provides the bid/ask prices and our order signals are generated there
        #bar data callback is set at line 381 :: bars.updateEvent += self.onBarUpdate

    def addTableRow(self, table, row_data):
        row = table.rowCount()

        table.setRowCount(row + 1)
        col = 0
        for item in row_data:
            cell = qt.QTableWidgetItem(str(item))
            table.setItem(row, col, cell)
            col += 1

    def onConnectButtonClicked(self, _):
        logging.debug("isconnected: " + str(self.ib.isConnected()))
        if self.ib.isConnected():
            self.ib.disconnect()
            #logging.debug("clearing data")
            #self.table.clearData()
            self.connectButton.setText('Connect')
            #logging.debug("done")
        else:
            logging.debug("trying to connect")
            self.ib.connect('127.0.0.1', 7497, clientId=1)  # *self.connectInfo)
            logging.debug("connected - ")  # + self.ib.isConnected())
            # self.ib.reqMarketDataType(2)
            self.connectButton.setText('Disconnect')
            self.ib.reqAccountSummary() #to avail the available cash

    async def accountSummaryAsync(self, account: str = '') -> \
            List[AccountValue]:
        if not self.wrapper.acctSummary:
            await self.reqAccountSummaryAsync()
        if account:
            return [v for v in self.wrapper.acctSummary.values()
                    if v.account == account]
        else:
            return list(self.wrapper.acctSummary.values())

    def accountSummary(self, account: str = '') -> List[AccountValue]:
        #if (account.tag == 'EquityWithLoanValue'):
        if (account.tag == 'BuyingPower'):
            accVal: float = 0.0
            accVal = account.value
            #self.availableCash = float(accVal)
            #self.availableCash = round(self.availableCash, 2)
            availableCash = float(accVal)
            availableCash = round(availableCash, 2)
            self.availableCash1 += availableCash
            logging.info('available cash - ' + str(self.availableCash))
        logging.debug("account summary:: " + str(account.account) + " " + account.tag + " " + account.value)

        return []

    def onCancelAllButtonClicked(self):
        logging.info("Cancelling all open orders")
        self.reqGlobalCancel()

    def textchanged(text):
        print("contents of text box: " + text)

    def onDisplayButtonClicked(self, _):
        logging.debug("MA values")
        for ma in self.MAList:
            logging.debug("symbol - " + " " + ma.symbol)
            logging.debug(str(ma.firstmaMajor) + " " + str(ma.firstma200) + " " + str(ma.firstSignal) + " " + str(
                ma.maMajor) + " " + str(ma.ma200))
        for x in self.MADict:
            logging.debug(x)
        for x in self.MADict.values():
            logging.debug("dict values - " + str(x.firstSignal) + " " + x.symbol + " " + str(x.firstmaMajor) + " " + str(
                x.firstma200) + " " + str(x.maMajor) + " " + str(x.ma200))

    def onClosePosButtonClicked(self):
        logging.info("Closing all positions")
        self.closePos = True
        self.ib.reqPositions()

    def onReqData(self):
        #self.reqGlobalCancel()

        """for symbol in ('TSLA', 'IBM', 'MSFT', 'FB'):
            logging.debug("requesting for " + symbol)"""
            # self.reqTickPrice(f"Stock('{symbol}', 'SMART', 'USD')")
            # self.add_historical(f"Stock('{symbol}', 'SMART', 'USD')")

        for symbol in ('EURUSD', 'USDJPY', 'EURGBP', 'USDCAD',
                       'EURCHF', 'AUDUSD', 'AUDCAD', 'NZDUSD', 'GBPUSD'):
            self.reqTickPrice(f"Forex('{symbol}')")
            self.add_historical(f"Forex('{symbol}')")

            row_1 = [symbol, '', '', '', '', '']
            print(self.table.rowCount())
            if (symbol in self.rowDict.keys()):
                print(symbol + " is present in the table")
                return
            self.rowDict[symbol] = self.table.rowCount()
            self.addTableRow(self.table, row_1)

    def onReqDataButtonClicked(self):
        print("Requesting data for " + self.symbolInput.text())
        symbol = self.symbolInput.text()
        #date = self.dateInput.text()
        #strike = self.strikeInput.text()
        #right = self.rightInput.text()
        self.wma1Val = int(self.wma1Input.text())
        self.wma2Val = int(self.wma2Input.text())
        self.table.setHorizontalHeaderItem(1, qt.QTableWidgetItem('WMA { ' + str(self.wma1Val) + ' }'))
        self.table.setHorizontalHeaderItem(2, qt.QTableWidgetItem('WMA { ' + str(self.wma2Val) + ' }'))
        #return
        type = self.typeInput.text()
        if(type == "Forex"):
            print("Requesting for " + symbol)
            self.reqTickPrice(f"Forex('{symbol}')")
            self.add_historical(f"Forex('{symbol}')")
        currency = self.currencyInput.text()
        exchange = self.exchangeInput.text()
        if(type == "Stock"):
            print("symbol currency and exch - " + symbol + " " + currency + " " + exchange)
            self.reqTickPrice(f"Stock('{symbol}', '{exchange}', '{currency}')")
            self.add_historical(f"Stock('{symbol}', '{exchange}', '{currency}')")

        row_1 = [symbol, '', '', '', '', '']
        print(self.table.rowCount())
        if(symbol in self.rowDict.keys()):
            print(symbol + " is present in the table")
            return
        self.rowDict[symbol] = self.table.rowCount()
        self.addTableRow(self.table, row_1)

    def reqTickPrice(self, text=''):
        logging.debug("text - " + text)
        text = text or self.edit.text()
        if text:
            contract = eval(text)
            print("contract symbol is " + contract.symbol)
            if(self.ib.isConnected()):
                self.ib.reqMktData(contract, '', False, False, None)
                logging.debug("requesting mkt data for " + text)

    def avg(self, x, y):
        #print(type(x), x.shape, type(x[0]))
        return np.average(x, weights=np.arange(1, y))

    def normalAvg(self, x):
        return np.average(x)

    def add_historical(self, text=''):
        logging.debug("text - " + text)
        text = text or self.edit.text()
        if text:
            logging.debug('eval text ')  # + eval(text))
            contract = eval(text)
            print("contract symbol is " + contract.symbol)
            logging.debug("requesting historical and mkt data for " + text)
            barVal = (int(self.wma2Val) * 60) + 60
            barValStr = str(barVal) + " S"
            print("barMin - " + str(barVal) + " " + barValStr)
            #return
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=barValStr, #'3060 S',
                barSizeSetting='1 min',
                whatToShow='BID',
                useRTH=True,
                formatDate=1,
                keepUpToDate=True)
            #self.ib.reqMktData(contract, '', False, False, None)
            print(bars)
            logging.debug("sectype " + str(
                bars.reqId) + " " + str(bars.contract.conId) + " " + bars.contract.secType + " " + bars.contract.symbol + " " + bars.contract.currency)
            #self.table.addHistoricalData(bars.reqId, contract)
            df = util.df(bars)
            close = pd.DataFrame(df, columns=['close'])
            logging.debug("close ")
            logging.debug(close)
            #closeListMinor = np.array(close[-self.wma1Val:].values.tolist())
            closeListMinor = np.array(close[-10:].values.tolist())

            closeList20 = np.array(close[-20:].values.tolist())
            closeListMajor = np.array(close[-self.wma2Val:].values.tolist())
            print(close)
            print(closeListMinor)
            print(str(len(closeListMinor)) + " " + str(len(np.arange(1, 11))))
            newcloseListMinor = closeListMinor.reshape(-1)
            newCloseList20 = closeList20.reshape(-1)
            newcloseListMajor = closeListMajor.reshape(-1)
            print(closeListMinor.shape)
            print(newcloseListMinor.shape)
            maMinor = self.avg(newcloseListMinor, self.wma1Val + 1)#, weights=np.arange(1, 11)))
            ma20 = self.normalAvg(newCloseList20) # weights=np.arange(1, 21))
            maMajor = self.avg(newcloseListMajor, self.wma2Val + 1) #weights=np.arange(1, 51))
            ma = MovingAverages(self.ib, closeList20, contract.symbol, maMinor, ma20, maMajor)
            symbol = contract.symbol + (contract.currency if contract.secType == 'CASH'
                                        else '')
            self.barData[symbol] = bars
            logging.info("symbol - " + symbol)
            self.MADict[symbol] = ma
            self.MAList.append(ma)
            bars.updateEvent += self.onBarUpdate #adding the callback for bar updates
            logging.debug("reqid is " + str(
                bars.reqId) + " for " + bars.contract.symbol + " " + bars.contract.currency + " , sectype - " + bars.contract.secType)

    def error_cb(self, reqId, errorCode, errorString, contract):
        logging.error("error: " + str(reqId) + " , " + str(errorCode) + " , " + str(errorString))
        logging.error("string - " + str(errorString))
        """if(errorCode == 1100):
            logging.error("Connectivity between IB and TWS has been lost")
            self.isConnectionBroken = True
        if (errorCode == 1300):
            logging.error("socket connection dropped")
            self.isConnectionBroken = True
        if(errorCode == 2105):
            logging.error("HMDS data farm connection is broken")
        if ((errorCode == 2104 or errorCode == 2106) and self.isConnectionBroken == True):
            logging.info("HMDS data farm connection has been restored")
            self.reqData()"""


    def reqGlobalCancel(self):
        """
        Cancel all active trades including those placed by other
        clients or TWS/IB gateway.
        """
        self.ib.reqGlobalCancel()
        logging.info('reqGlobalCancel')

    def position_cb(self, position):
        if(position.position == 0):
            return
        if(self.closePos == True):
            symbol = position.contract.symbol + (
                position.contract.currency if position.contract.secType == 'CASH'
                else '')
            logging.info("position for " + position.account + " - " + symbol + " " + position.contract.exchange + " " + position.contract.primaryExchange + " :: " + str(position.position) + "  Avg Cost - " + str(position.avgCost))
            if(position.position > 0):
                action = 'SELL'
            else:
                action = 'BUY'

            exchange = 'IDEALPRO' if position.contract.exchange == '' else 'SMART'
            currency = position.contract.currency
            secType = position.contract.secType

            order = Order()
            order.orderId = self.ib.client.getReqId()
            order.action = action
            order.orderType = "MKT"
            order.exchange = exchange
            if(position.position < 0):
                position = -(position.position)

            print("position - " + str(position))
            quantity = position
            order.totalQuantity = quantity
            contract = Contract()
            contract.symbol = symbol
            contract.secType = secType
            contract.currency = currency

            contract.exchange = exchange
            contract.primaryExchange = exchange

            trade = self.ib.placeOrder(contract, order)

    def order_status_cb(self, trade):
        if (self.closePos == True or not self.MADict):
            return
        symbol = trade.contract.symbol + (trade.contract.currency if trade.contract.secType == 'CASH' else '')
        logging.info("OrderId, Status, avgFillPrice, filled and remaining for  " + symbol + " - " + str(trade.order.orderId) + " " + trade.orderStatus.status  + " " + str(trade.orderStatus.avgFillPrice) + " " + str(trade.orderStatus.filled) + " " + str(trade.orderStatus.remaining))

        ma = self.MADict[symbol]
        """if(ma.isOrderActive == True):
            if(ma.GCCheck == False):
                logging.info("checking for gcorder")
            if(ma.GCCheck == True):
                logging.info("checking for dcorder")"""

    def exec_details_cb(self, trade, fill):
        if(self.closePos == True or not self.MADict):
            return
        symbol = trade.contract.symbol + (
            trade.contract.currency if trade.contract.secType == 'CASH'
            else '')
        ma = self.MADict[symbol]

        remaining = trade.remaining()
        if (trade.isDone() == False):
            logging.info("trade isnt done yet for " + symbol + " , remaining - " + str(remaining))

        #calculations for parent order
        if(trade.order.orderId == ma.orderObj.pOrderId):
            if(remaining == 0):
                if(trade.order.action == 'BUY'):
                    self.availableCash -= (fill.execution.cumQty * fill.execution.avgPrice)
                if(trade.order.action == 'SELL'):
                    self.availableCash += (fill.execution.cumQty * fill.execution.avgPrice)

        #calculations for tp/sl orders
        if (trade.order.orderId == ma.orderObj.tpOrderId or trade.order.orderId == ma.orderObj.slOrderId):
            if (remaining == 0):
                self.totalPos -= 1
                if (trade.order.action == 'BUY'):
                    self.availableCash -= (fill.execution.cumQty * fill.execution.avgPrice)
                if (trade.order.action == 'SELL'):
                    self.availableCash += (fill.execution.cumQty * fill.execution.avgPrice)

                ma.bought = False
                ma.sold = False
                self.MADict[symbol] = ma

        isdone = trade.isDone()
        logging.info("exec details for " + symbol + " with orderid " + str(fill.execution.orderId))

        #if(fill.execution.side == "Sell"):
        #    self.availableCash += fill.execution.price

    #If a new bar has been added then hasNewBar is True
    #Moving average calculation is done over here
    def onBarUpdate(self, bars, hasNewBar):
        self.xs.append(dt.datetime.now().strftime('%H:%M:%S.%f'))
        symbol = bars.contract.symbol + (
            bars.contract.currency if bars.contract.secType == 'CASH'
            else '')
        logging.debug("bar update " + str(bars.endDateTime) + " " + str(hasNewBar) + " for " + symbol + " " + bars.whatToShow)
        logging.debug(bars[-1])

        if (symbol in self.MADict):
            ma = self.MADict[symbol]
            if (hasNewBar == True): #ma calculations is done when a new bar is added
                if(ma.firstBar == True):
                    ma.firstBar = False
                ma.prevPrice = ma.prevClose
                ma.prev_maMinor = ma.maMinor
                ma.prev_maMajor = ma.maMajor
                #df = util.df(bars)
                self.barData[symbol].append(bars[-1])
                df = util.df(self.barData[symbol])
                close = pd.DataFrame(df, columns=['close'])
                closeListMinor = np.array(close[-self.wma1Val:].values.tolist())
                closeList20 = np.array(close[-20:].values.tolist())
                closeListMajor = np.array(close[-self.wma2Val:].values.tolist())
                newcloseListMinor = closeListMinor.reshape(-1)
                newCloseList20 = closeList20.reshape(-1)
                newcloseListMajor = closeListMajor.reshape(-1)
                ma.maMinor = self.avg(newcloseListMinor, self.wma1Val + 1) #np.average(bars[10:], weights = np.arange(1, 11))
                ma.ma20 = self.normalAvg(newCloseList20) #np.average(bars[20:], weights=np.arange(1, 21))
                ma.maMajor = self.avg(newcloseListMajor, self.wma2Val + 1) #np.average(bars[50:], weights=np.arange(1, 51))
                ma.ma20Array = newCloseList20
                self.MADict[symbol] = ma
                maMinor = str(round(ma.maMinor, 6))
                maMajor = str(round(ma.maMajor, 6))
                maMinorCell = qt.QTableWidgetItem(maMinor)
                maMajorCell = qt.QTableWidgetItem(maMajor)
                logging.info("setting table items to " + maMinor + " " + maMajor)
                self.table.setItem(self.rowDict[symbol], 1, maMinorCell)
                self.table.setItem(self.rowDict[symbol], 2, maMajorCell)
                return
            ma.prevClose = bars[-1].close
            self.MADict[symbol] = ma
            logging.debug("prev close is " + str(bars[-1].close))
        else:
            return

    def onPendingTickers(self, tickers):
        for ticker in tickers:
            for col, header in enumerate(self.headers):
                if col == 0:
                    continue
                val = getattr(ticker, header)
                symbol = ticker.contract.symbol + (
                    ticker.contract.currency if ticker.contract.secType == 'CASH'
                    else '')
                if(symbol in self.MADict):
                    ma = self.MADict[symbol]
                    logging.debug("Values - " + str(ticker.contract.secType) + " " + str(
                        ticker.contract.conId) + " " + symbol + " " + str(header) + " " + str(col) + " val- " + str(
                        val))
                    if (str(header) == 'bid'):
                        ma.bid = val
                        self.MADict[symbol] = ma
                    if (str(header) == 'ask'):
                        ma.ask = val
                        self.MADict[symbol] = ma
                        val = round(((ma.bid + ma.ask)/2), 6)
                        if(math.isnan(val)):
                            return

                        maMinor = ma.maMinor
                        maMajor = ma.maMajor
                        prev_maMinor = ma.prev_maMinor
                        prev_maMajor = ma.prev_maMajor
                        logging.info("prevMAs and MAs - " + str(prev_maMinor) + " " + str(prev_maMajor) + " " + str(maMinor) + " " + str(maMajor))
                        #ma.prevPrice = val
                        if(maMajor == ''):
                            print("maMajor isnt available yet")
                            return

                        bbWidth = ma.getBBWidth()
                        logging.info("Bollinger band width is " + str(bbWidth))

                        if ticker.contract.secType == 'CASH':
                            tpMult = .0003
                            slMult = .00015
                        else:
                            tpMult = .0038
                            slMult = .0001

                        cash = lowerHundred(self.availableCash)
                        logging.info("ma values for " + symbol + " - " + str(ma.prevPrice) + " " + str(prev_maMinor)  + " " + str(val) + " " + str(maMinor) + " " + str(prev_maMajor) + " " + str(maMajor))
                        logging.info("priceCrossedAbovemaMinor and priceCrossedAbovemaMajor - " + str(ma.priceCrossedAbovemaMinor) + " " + str(ma.priceCrossedAbovemaMajor))
                        logging.info("priceCrossedBelowmaMinor and priceCrossedBelowmaMajor - " + str(
                            ma.priceCrossedBelowmaMinor) + " " + str(ma.priceCrossedBelowmaMajor))



                        #Condition 1 :: Purchase signal no1
                        if(ma.prevPrice > 0 and ma.prevPrice < prev_maMinor and val > maMinor and maMinor > 0): #checking if price crossed above maMinor
                            logging.info("price crossed above maMinor, ma.priceCrossedAbovemaMajor - " + str(ma.priceCrossedAbovemaMinor))
                            ma.priceCrossedAbovemaMinor = True
                            ma.priceCrossedBelowmaMinor = False
                            self.MADict[symbol] = ma

                            #IF THE BOLLINGER BAND WIDTH <0.0059 at the time to the PURCHASE SIGNAL is given, then CANCEL THE ORDER SYSTEMATICALLY
                            if (bbWidth < 0.0059): #
                                logging.info("returning as bollinger bandwidth is " + str(bbWidth))
                                ma.prevPrice = val
                                self.MADict[symbol] = ma
                                return

                            #If the PRICE curve crosses upward WMA 10 and WMA 50 then buy upward at the crossover point of the 2nd WMA (WmaMinor)
                            #line no 597:: ma.prevPrice < prev_maMinor and val > maMinor -> is the check for price crossing above maMinor
                            #ma.priceCrossedAbovemaMajor = true means price has already crossed above maMajor
                            if(ma.priceCrossedAbovemaMajor == True and ma.bought == False and self.totalPos < 3 ):
                                logging.info("Placing order for " + symbol)
                                ma.bought = True
                                self.totalPos += 1
                                tpPrice = ma.ask + (ma.ask * tpMult)
                                slPrice = ma.ask - (ma.ask * slMult)
                                bracket = self.ib.bracketOrder("BUY", lowerHundred(cash/ma.ask), ma.ask, round(tpPrice, 2), round(slPrice, 2))
                                bracket.parent.orderType = "MKT"
                                ma.orderObj.pOrderId = bracket.parent.orderId
                                ma.orderObj.pSide = "BUY"
                                ma.orderObj.tpOrderId = bracket.takeProfit.orderId
                                ma.orderObj.slOrderId = bracket.stopLoss.orderId
                                self.MADict[symbol] = ma
                                for order in bracket:
                                    orderTrade = self.ib.placeOrder(ticker.contract, order)
                                    orderTrade.orderStatus.status = "Submitted"

                        if (ma.prevPrice > 0 and ma.prevPrice < prev_maMajor and val > maMajor and maMajor > 0): #checking if price crossed above maMajor
                            logging.info("price crossed above maMajor, ma.priceCrossedAbovemaMinor - " + str(ma.priceCrossedAbovemaMinor))
                            ma.priceCrossedAbovemaMajor = True
                            ma.priceCrossedBelowmaMajor = False
                            self.MADict[symbol] = ma

                            #IF THE BOLLINGER BAND WIDTH <0.0059 at the time to the PURCHASE SIGNAL is given, then CANCEL THE ORDER SYSTEMATICALLY
                            if (bbWidth < 0.0059):
                                logging.info("returning as bollinger bandwidth is " + str(bbWidth))
                                ma.prevPrice = val
                                self.MADict[symbol] = ma
                                return

                            #If the PRICE curve crosses upward WMA 10 and WMA 50 then buy upward at the crossover point of the 2nd WMA (WmaMajor)
                            #line no 628:: ma.prevPrice < prev_maMajor and val > maMajor -> is the check for price crossing above maMajor
                            #ma.priceCrossedAbovemaMinor = true means price has already crossed above maMinor
                            if (ma.priceCrossedAbovemaMinor == True and ma.bought == False and self.totalPos < 3):
                                logging.info("Placing order for " + symbol)
                                ma.bought = True
                                self.totalPos += 1
                                tpPrice = ma.ask + (ma.ask * tpMult)
                                slPrice = ma.ask - (ma.ask * slMult)
                                bracket = self.ib.bracketOrder("BUY", lowerHundred(cash/ma.ask), ma.ask, round(tpPrice, 2),
                                                       round(slPrice, 2))
                                bracket.parent.orderType = "MKT"
                                ma.orderObj.pOrderId = bracket.parent.orderId
                                ma.orderObj.pSide = "BUY"
                                ma.orderObj.tpOrderId = bracket.takeProfit.orderId
                                ma.orderObj.slOrderId = bracket.stopLoss.orderId
                                self.MADict[symbol] = ma
                                for order in bracket:
                                    orderTrade = self.ib.placeOrder(ticker.contract, order)
                                    orderTrade.orderStatus.status = "Submitted"

                        #CONDITION 2 :: purchase signal no2
                        if (ma.prevPrice > prev_maMinor and prev_maMinor > 0 and val < maMinor and val > 0):
                            logging.info("price crossed below maMinor, ma.priceCrossedBelowmaMajor - " + str(ma.priceCrossedBelowmaMajor))
                            ma.priceCrossedBelowmaMinor = True
                            ma.priceCrossedAbovemaMinor = False
                            self.MADict[symbol] = ma

                            #IF THE BOLLINGER BAND WIDTH <0.0059 at the time to the PURCHASE SIGNAL is given, then CANCEL THE ORDER SYSTEMATICALLY
                            if (bbWidth < 0.0059):
                                logging.info("returning as bollinger bandwidth is " + str(bbWidth))
                                ma.prevPrice = val
                                self.MADict[symbol] = ma
                                return

                            #If the PRICE curve crosses WMA 10 and WMA 50 downwards then sell short at the crossover point of the 2nd WMA (WmaMinor)
                            #line no 660:: ma.prevPrice > prev_maMinor and val < maMinor -> is the check for price crossing downwards maMinor
                            #ma.priceCrossedBelowmaMajor = true means price has already crossed below maMajor
                            if (ma.priceCrossedBelowmaMajor == True and ma.sold == False and self.totalPos < 3):
                                logging.info("Placing order for " + symbol)
                                ma.sold = True
                                self.totalPos += 1
                                tpPrice = ma.bid + (ma.bid * tpMult)
                                slPrice = ma.bid - (ma.bid * slMult)
                                bracket = self.ib.bracketOrder("SELL", lowerHundred(cash/ma.bid), ma.bid, round(tpPrice, 2),
                                                       round(slPrice, 2))
                                bracket.parent.orderType = "MKT"
                                ma.orderObj.pOrderId = bracket.parent.orderId
                                ma.orderObj.pSide = "SELL"
                                ma.orderObj.tpOrderId = bracket.takeProfit.orderId
                                ma.orderObj.slOrderId = bracket.stopLoss.orderId
                                self.MADict[symbol] = ma
                                for order in bracket:
                                    orderTrade = self.ib.placeOrder(ticker.contract, order)
                                    orderTrade.orderStatus.status = "Submitted"

                        #checking if price crossed below maMajor
                        if (ma.prevPrice > prev_maMajor and prev_maMajor > 0 and val < maMajor and val > 0):
                            logging.info("price crossed below maMajor, ma.priceCrossedBelowmaMinor - " + str(ma.priceCrossedBelowmaMinor))
                            ma.priceCrossedBelowmaMajor = True
                            ma.priceCrossedAbovemaMajor = False
                            self.MADict[symbol] = ma

                            #IF THE BOLLINGER BAND WIDTH <0.0059 at the time to the PURCHASE SIGNAL is given, then CANCEL THE ORDER SYSTEMATICALLY
                            if (bbWidth < 0.0059):
                                logging.info("returning as bollinger bandwidth is " + str(bbWidth))
                                ma.prevPrice = val
                                self.MADict[symbol] = ma
                                return

                            #If the PRICE curve crosses WMA 10 and WMA 50 downwards then sell short at the crossover point of the 2nd WMA (WmaMajor)
                            # line no 692:: ma.prevPrice > prev_maMajor and val < maMajor -> is the check for price crossing downwards maMajor
                            # ma.priceCrossedBelowmaMinor = true means price has already crossed below maMinor
                            if (ma.priceCrossedBelowmaMinor == True and ma.sold == False and self.totalPos < 3):
                                logging.info("Placing order for " + symbol)
                                ma.sold = True
                                self.totalPos += 1
                                tpPrice = ma.bid + (ma.bid * tpMult)
                                slPrice = ma.bid - (ma.bid * slMult)

                                bracket = self.ib.bracketOrder("SELL", lowerHundred(cash/ma.bid), ma.bid, round(tpPrice, 2),
                                                       round(slPrice, 2))
                                bracket.parent.orderType = "MKT"
                                ma.orderObj.pOrderId = bracket.parent.orderId
                                ma.orderObj.pSide = "SELL"
                                ma.orderObj.tpOrderId = bracket.takeProfit.orderId
                                ma.orderObj.slOrderId = bracket.stopLoss.orderId
                                self.MADict[symbol] = ma
                                for order in bracket:
                                    orderTrade = self.ib.placeOrder(ticker.contract, order)
                                    orderTrade.orderStatus.status = "Submitted"

                        #IF WMA 10 > WMA 50, then trend to BUY, therefore CANCEL all short sell orders.
                        if(maMinor > maMajor):
                            if(ma.orderObj.pSide == "SELL"):
                                self.ib.cancelOrder(ma.orderObj.pOrder)
                                ma.sold = ma.bought = False
                                self.MADict[symbol] = ma
                                self.totalPos -= 1

                        #IF WMA 10 < WMA 50, then trend SELL, therefore CANCEL all buy orders.
                        if (maMinor > maMajor):
                            if (ma.orderObj.pSide == "BUY"):
                                self.ib.cancelOrder(ma.orderObj.pOrder)
                                ma.sold = ma.bought = False
                                self.MADict[symbol] = ma
                                self.totalPos -= 1

                        ma.prevPrice = val
                        self.MADict[symbol] = ma

                else:
                    logging.error(symbol + " key is not present")




    def TrailBracketOrder(self, parentOrderId, childOrderId, action, quantity, limitPrice, trailAmount):

        # This will be our main or "parent" order
        parent = Order()
        parent.orderId = parentOrderId
        parent.action = action
        parent.orderType = "LMT"
        parent.totalQuantity = quantity
        parent.lmtPrice = limitPrice
        parent.transmit = False

        stopLoss = Order()
        stopLoss.orderId = childOrderId
        logging.info("Action is " + action)
        if action == "Buy":
            stopLoss.action = "Sell"
            stopLoss.trailStopPrice = limitPrice - (limitPrice * .02)
        if action == "Sell":
            stopLoss.action = "Buy"
            stopLoss.trailStopPrice = limitPrice + (limitPrice * .02)
        stopLoss.orderType = "TRAIL"
        stopLoss.auxPrice = limitPrice #trailAmount
        stopLoss.totalQuantity = quantity
        stopLoss.parentId = parentOrderId
        stopLoss.transmit = True

        bracketOrder = [parent, stopLoss]
        return bracketOrder

    def closeEvent(self, ev):
        logging.debug("closing")
        asyncio.get_event_loop().stop()


if __name__ == '__main__':
    util.patchAsyncio()
    util.useQt()
    # util.useQt('PySide2')
    window = Window('127.0.0.1', 7497, 1)
    window.resize(600, 400)
    window.show()
    IB.run()
    loop = asyncio.get_event_loop()
