# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_prices_from_excel as m

def main():
    m.import_customer("上海万向钱潮A-A", m.parse_shanghai)

m.main = main

if __name__ == "__main__":
    m.main()
