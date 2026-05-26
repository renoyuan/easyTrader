#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PROJECT_NAME:  demo.py
# CREATE_TIME: 2025/5/23 16:14
# E_MAIL: renoyuan@foxmail.com
# AUTHOR: reno
# NOTE:
import yfinance as yf

dat = yf.Ticker("MSFT")

# get historical market data
dat.history(period='1mo')

# options
dat.option_chain(dat.options[0]).calls

# get financials
dat.balance_sheet
dat.quarterly_income_stmt

# dates
dat.calendar

# general info
dat.info

# analysis
dat.analyst_price_targets

# websocket
dat.live()