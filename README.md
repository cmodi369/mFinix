# mFinix
Open source multi asset portfolio analytics platform written in Python.

## Limitations
- yfinance library is used to pull stock specific information. Missing details of specific stock can lead to missing transactions in the tool.
   - Historical information of merged entity can be missing for mergers.
   - Name change can lead to missing details on trades with older name.
