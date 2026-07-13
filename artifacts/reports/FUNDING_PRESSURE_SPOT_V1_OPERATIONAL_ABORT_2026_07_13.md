# Funding-pressure Spot V1 operational abort

Status: **ABORTED BEFORE SELECTION — no strategy verdict**

`FUNDING-PRESSURE-SPOT-G1-G11-V1` started from clean commit
`528f8a5020fc45105fda1fd180732e93fec779e9`. The Decimal development phase was computed in
memory, then the first external worker failed to import the repository-local `engines` package.
The runner failed closed and removed its temporary directory.

Verified consequences:

- no selection artifact or selected StrategyVersion was created;
- validation, reserve, full-history, and period strategy evaluation did not run;
- no campaign output directory or metric artifact was created;
- no result was inspected or used to change polarity, lookback, threshold, costs, gates, or rules;
- no network, credential, venue, derivative position, bot, order, paper/demo/live state, or
  execution authority was touched.

V1 is closed as an operational abort under its frozen mismatch rule. V2 may change only the
external-worker repository import bootstrap. It inherits the complete V1 strategy/statistical
contract by content hash; the family-unseen validation and reserve remain untouched.
