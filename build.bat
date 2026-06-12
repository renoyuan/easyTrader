@echo off
chcp 65001 >nul
set SRC_DIR=%~dp0
pyinstaller --onedir --name "easyTrader" --collect-all numpy --collect-all matplotlib --collect-all akshare --add-data "%SRC_DIR%trader\data;trader\data" --add-data "%SRC_DIR%trader;trader" --hidden-import trader.processor.feature --hidden-import trader.scorer.buffett --hidden-import trader.scorer.renoyuan --hidden-import trader.scorer.xubin --hidden-import trader.scorer.xuxiang --hidden-import trader.scorer.fang_laoge --hidden-import trader.scorer.graham --hidden-import trader.scorer.market_scanner --exclude-module mkl "%SRC_DIR%trader\gui_app.py"
