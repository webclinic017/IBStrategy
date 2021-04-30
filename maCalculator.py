from datetime import datetime
from random import randint

class OrderObject:

    def __init__(self, symbol, totalShares, status):
        self.symbol = symbol
        self.totalShares = totalShares
        self.status = status

class MovAvgCalculator:

    def __init__(self, starting_list=None, window_duration=10):
        self.moving_average = None
        self.prev_ma = None
        if starting_list:
            self.my_list = starting_list
            self.sum = sum(starting_list)
            self.count = window_duration
            self.calculate_average()
        else:
            self.my_list = []
            self.sum = 0
            self.count = 0
        self.window_duration = window_duration

    def append(self, item):
        list.append(self.my_list, item)
        if len(self.my_list) > self.window_duration:
            del self.my_list[0]
        self.sum += item
        if(len(self.my_list) < self.window_duration):
            return
        self.prev_ma = self.moving_average
        self.prev_ma = self.moving_average
        self.calculate_average()

    def calculate_average(self):
        self.moving_average = self.sum / self.window_duration

